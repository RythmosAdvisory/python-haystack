import sys

__PROXIES = {}

def reset_ctypes():
    """Reset sys.module to import the host ctypes module."""
    # remove all refs to the ctypes modules or proxies
    if 'ctypes' in sys.modules:
        del sys.modules['ctypes']
    # import the real one
    import ctypes
    return ctypes

def load_ctypes_default():
    """Load sys.module with a default host-mimicking ctypes module proxy."""
    reset_ctypes()
    import ctypes
    # get the hosts' types
    longsize = ctypes.sizeof(ctypes.c_long)
    pointersize = ctypes.sizeof(ctypes.c_void_p)
    longdoublesize = ctypes.sizeof(ctypes.c_longdouble)
    return reload_ctypes(longsize, pointersize, longdoublesize)


def reload_ctypes(longsize, pointersize, longdoublesize):
    """Load sys.modle with a tuned ctypes module proxy."""
    if (longsize, pointersize, longdoublesize) in __PROXIES:
        instance = __PROXIES[(longsize, pointersize, longdoublesize)]
        set_ctypes(instance)
        return instance
    instance = CTypesProxy(longsize, pointersize, longdoublesize)
    __PROXIES[(longsize, pointersize, longdoublesize)] = instance
    return instance

def set_ctypes(ctypesproxy):
    """Load Change the global ctypes module to a specific proxy instance"""
    if not isinstance(ctypesproxy, CTypesProxy):
        raise TypeError('CTypesProxy instance expected.')
    sys.modules['ctypes'] = ctypesproxy
    return sys.modules['ctypes']

class CTypesProxy(object):
    """# TODO: set types in config.Types
    # ctypeslib generate python code based on config.Types.*
    # never import ctypes, but proxy always through instance of config.
    # flow:
    # a) init config with size/etc.
    # b) init model instance with config instance
    # c) create structure & Union proxied in model instance
    # d) refer to config through dynamically generated Structure/Union classes.

    # sys.modules['ctypes'] = proxymodule/instance

    By default do not load this in model
    """
    def __init__(self, longsize, pointersize, longdoublesize):
        """Proxies 'the real' ctypes."""
        self.proxy = True
        self.__longsize = longsize
        self.__pointersize = pointersize
        self.__longdoublesize = longdoublesize
        # remove all refs to the ctypes modules or proxies
        reset_ctypes()
        # import the real one
        import ctypes
        self.__real_ctypes = ctypes
        if hasattr(ctypes,'proxy'):
            raise RuntimeError('base ctype should not be a proxy')
        # copy every members
        for name in dir(ctypes):
            if not name.startswith('__'):
                setattr(self, name, getattr(ctypes, name))
        del ctypes
        # replace it.
        sys.modules['ctypes'] = self
        self.__init_types()
        pass        

    def __init_types(self):
        self.__set_void()
        self.__set_int128()
        self.__set_long()
        self.__set_float()
        self.__set_pointer()
        self.__set_records()
        return

    def __set_void(self):
        self.void = None
        return
        
    def __set_int128(self):
        self.c_int128 = self.__real_ctypes.c_ubyte*16
        self.c_uint128 = self.c_int128
        return

    def __set_long(self):
        # use host type if target is the same
        if self.sizeof(self.__real_ctypes.c_long) == self.__longsize:
            return
        if self.__longsize == 4:
            self.c_long = self.__real_ctypes.c_int32
            self.c_ulong = self.__real_ctypes.c_uint32
        elif self.__longsize == 8:
            self.c_long = self.__real_ctypes.c_int64
            self.c_ulong = self.__real_ctypes.c_uint64
        else:
            raise NotImplementedError('long size of %d is not handled'%(self.__longsize))

    def __set_float(self):
        # use host type if target is the same
        if self.sizeof(self.__real_ctypes.c_longdouble) == self.__longdoublesize:
            return
        self.c_longdouble = self.c_ubyte*self.__longdoublesize
        return

    def __set_pointer(self):
        # TODO: c_char_p ?
        # if host pointersize is same as target, keep ctypes pointer function.
        if self.sizeof(self.__real_ctypes.c_void_p) == self.__pointersize:
            return
        # get the replacement type.
        if self.__pointersize == 4:
            replacement_type = self.__real_ctypes.c_uint32
            replacement_type_char = self.__real_ctypes.c_uint32._type_
        elif self.__pointersize == 8:
            replacement_type = self.__real_ctypes.c_uint64
            replacement_type_char = self.__real_ctypes.c_uint64._type_
        else:
            raise NotImplementedError('pointer size of %d is not handled'%(self.__pointersize))
        POINTERSIZE = self.__pointersize
        # required to access _ctypes
        import _ctypes
        # Emulate a pointer class using the approriate c_int32/c_int64 type
        # The new class should have :
        # ['__module__', 'from_param', '_type_', '__dict__', '__weakref__', '__doc__']
        def POINTER_T(pointee):
            # a pointer should have the same length as LONG
            fake_ptr_base_type = replacement_type
            # specific case for c_void_p
            if pointee is None: # VOID pointer type. c_void_p.
                pointee = type(None) # ctypes.c_void_p # ctypes.c_ulong
                clsname = 'c_void'
            else:
                clsname = pointee.__name__
            # make template
            class _T(_ctypes._SimpleCData,):
                _type_ = replacement_type_char
                _subtype_ = pointee
                def _sub_addr_(self):
                    return self.value
                def __repr__(self):
                    return '%s(%d)'%(clsname, self.value)
                def contents(self):
                    raise TypeError('This is not a ctypes pointer.')
                def __init__(self, **args):
                    raise TypeError('This is not a ctypes pointer. It is not instanciable.')
            _class = type('LP_%d_%s'%(POINTERSIZE, clsname), (_T,),{}) 
            return _class
        self.POINTER = POINTER_T
        return

    def __set_records(self):
        """Replaces ctypes.Structure and ctypes.Union with their LoadableMembers
        counterparts. Add a CString type.
        MAYBE FIXME: These root types will only be valid when the ctypes record is 
        used with the adequate CTypesProxy.
        """
        class CString(self.__real_ctypes.Union):
            """
            This is our own implementation of a string for ctypes.
            ctypes.c_char_p can not be used for memory parsing, as it tries to load 
            the string itself without checking for pointer validation.

            it's basically a Union of a string and a pointer.
            """
            _fields_=[
            #("string", self.__real_ctypes.original_c_char_p),
            ("string", self.c_char_p),
            ("ptr", self.POINTER(self.c_ubyte) )
            ]
            def toString(self):
                if not bool(self.ptr):
                    return "<NULLPTR>"
                if hasRef(CString, getaddress(self.ptr)):
                    return getRef(CString, getaddress(self.ptr) )
                log.debug('This CString was not in cache - calling toString was not a good idea')
                return self.string
                pass
        # and there we have it. We can load basicmodel
        self.CString = CString
        
        ## change LoadableMembers structure given the loaded plugins
        import basicmodel
        if True:
            import listmodel
            heritance = tuple([listmodel.ListModel,basicmodel.LoadableMembers])
        else:
            heritance = tuple([basicmodel.LoadableMembers])
        self.LoadableMembers = type('LoadableMembers', heritance, {})

        class LoadableMembersUnion(self.__real_ctypes.Union, self.LoadableMembers):
            pass
        class LoadableMembersStructure(self.__real_ctypes.Structure, self.LoadableMembers):
            pass
        # create local POPO ( lodableMembers )
        #createPOPOClasses(sys.modules[__name__] )
        self.LoadableMembersStructure_py = type('%s.%s_py'%(__name__, LoadableMembersStructure),( basicmodel.pyObj ,),{})
        self.LoadableMembersUnion_py = type('%s.%s_py'%(__name__, LoadableMembersUnion),( basicmodel.pyObj ,),{})
        # register LoadableMembers 

        # we need model to be initialised.
        self.Structure = LoadableMembersStructure
        self.Union = LoadableMembersUnion
        return


    #import sys
    #from inspect import getmembers, isclass
    #self = sys.modules[__name__]
    def _p_type(s):
        """CHECKME: Something about self reference in structure fields in ctypeslib"""
        return dict(getmembers(self, isclass))[s]

    def get_real_ctypes_type(self, typename):
        return getattr(self.__real_ctypes, typename)

    def call_real_ctypes_method(self, fname, **kv):
        return getattr(self.__real_ctypes, fnname)(**kv)

    def __str__(self):
        return "<haystack.types.CTypesProxy-%d:%d:%d-%x>"%(self.__longsize,self.__pointersize,self.__longdoublesize,id(self))

    # TODO implement haystack.utils.bytestr_fmt here
