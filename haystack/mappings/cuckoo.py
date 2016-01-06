# -*- coding: utf-8 -*-

"""
Cuckoo process dump backed memory_handler.
"""


import os
import sys
import logging
import mmap
import struct
from functools import partial

from haystack.mappings import base
from haystack.mappings import file
from haystack.abc import interfaces
from haystack import target

log = logging.getLogger('cuckoo')

PAGE_READONLY = 0x00000002
PAGE_READWRITE = 0x00000004
PAGE_WRITECOPY = 0x00000008
PAGE_EXECUTE = 0x00000010
PAGE_EXECUTE_READ = 0x00000020
PAGE_EXECUTE_READWRITE = 0x00000040
PAGE_EXECUTE_WRITECOPY = 0x00000080

page_access = {
    PAGE_READONLY: "r--",
    PAGE_READWRITE: "rw-",
    PAGE_WRITECOPY: "rc-",
    PAGE_EXECUTE: "r-x",
    PAGE_EXECUTE_READ: "r-x",
    PAGE_EXECUTE_READWRITE: "rwx",
    PAGE_EXECUTE_WRITECOPY: "rcx",
}

class MMapProcessMapping(base.AMemoryMapping):
    """Process memory mapping using 1 file for all mappings """

    def __init__(self, mmap_content, start, end, permissions='r--',
                 offset=0, major_device=0, minor_device=0, inode=0, pathname=''):
        """mmap_content should be """
        base.AMemoryMapping.__init__(
            self,
            start,
            end,
            permissions,
            offset,
            major_device,
            minor_device,
            inode,
            pathname)
        self._backend = mmap_content
        self.offset = offset

    def read_word(self, addr):
        ws = self._target_platform.get_word_size()
        self._backend.seek(self.offset + addr - self.start, 0)
        data = self._backend.read(ws)
        if ws == 4:
            return struct.unpack('I', data)[0]
        elif ws == 8:
            return struct.unpack('Q', data)[0]

    def read_bytes(self, addr, size):
        self._backend.seek(self.offset + addr - self.start, 0)
        return self._backend.read(size)

    def read_struct(self, addr, struct):
        size = self._target_platform.get_target_ctypes().sizeof(struct)
        self._backend.seek(self.offset + addr - self.start, 0)
        instance = struct.from_buffer_copy(self._backend.read(size))
        instance._orig_address_ = addr
        return instance

    def read_array(self, addr, basetype, count):
        size = self._target_platform.get_target_ctypes().sizeof(basetype * count)
        self._backend.seek(self.offset + addr - self.start, 0)
        array = (basetype *count).from_buffer_copy(self._backend.read(size))
        return array

    def reset(self):
        pass


class CuckooProcessMapper(interfaces.IMemoryLoader):

    def __init__(self, procdump_filename):
        basename = os.path.basename(procdump_filename)
        # pid-1.dmp
        pid = basename.split('-')[0]
        log.debug("CuckooProcessMapper %s %p", basename, pid)
        self.pid = pid
        log.debug("pid: %s", self.pid)
        self.filename = procdump_filename
        self._memory_handler = None
        self._init_mappings()
        self._init_cuckoo('windows', 'I386', 5.1)

    def _init_mappings(self):
        content_file = open(self.filename, 'rb')
        fsize = os.path.getsize(self.filename)
        mmap_content = mmap.mmap(
                    content_file.fileno(),
                    fsize,
                    access=mmap.ACCESS_READ)
        log.debug("fsize: %d", fsize)
        maps = []
        # BUG ?
        # the last mapping is incomplete, and seems to be the PE file.
        while True:
            buf = content_file.read(24)
            if not buf:
                break
            row = struct.unpack("QIIII", buf)
            addr, size, state, typ, protect = row
            offset = content_file.tell()
            # check end of file
            if offset+size > fsize:
                log.warning('reducing last mapping size 0x%x -> 0x%x bytes', size, fsize - offset)
                size = fsize - offset
            end = addr + size
            mapping_1 = MMapProcessMapping(mmap_content, addr, end, page_access.get(protect), offset)
            maps.append(mapping_1)
            log.debug('%s size:0x%x start:0x%x end:0x%x max:0x%x', mapping_1, size, offset, offset + size, fsize)
            # for some reason it doesn't raise ValueError when seeking too far...
            content_file.seek(size, 1)
        #
        self.mappings = maps
        log.debug("nb maps: %d", len(self.mappings))
        return maps

    def _init_cuckoo(self, os_name, arch, major):
        # get profile for target ?
        # get the platform
        # get the proc name for pid x
        if os_name == "windows":
            os_name = ''
            if major == 5.1:
                os_name = 'winxp'
            elif major == 6.1:
                os_name = 'win7'
            #
            if arch == u'I386':
                self._target = target.TargetPlatform.make_target_win_32(os_name)
            else:
                self._target = target.TargetPlatform.make_target_win_64(os_name)
        else:
            if arch == u'I386':
                self._target = target.TargetPlatform.make_target_linux_32()
            else:
                self._target = target.TargetPlatform.make_target_linux_64()

        log.debug("target: %s", self._target)
        # create a folder for it
        h_name = self.filename + ".d"
        if not os.path.exists(h_name):
            os.mkdir(h_name)
        memory_handler = base.MemoryHandler(self.mappings, self._target, h_name)
        self._memory_handler = memory_handler

    def make_memory_handler(self):
        return self._memory_handler


PERMS_PROTECTION = dict(enumerate([
    '---',  # 'PAGE_NOACCESS',
    'r--',  # 'PAGE_READONLY',
    '--x',  # 'PAGE_EXECUTE',
    'r-x',  # 'PAGE_EXECUTE_READ',
    'rw-',  # 'PAGE_READWRITE',
    'rc-',  # 'PAGE_WRITECOPY',
    'rwx',  # 'PAGE_EXECUTE_READWRITE',
    'rcx',  # 'PAGE_EXECUTE_WRITECOPY',
]))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("basicmodel").setLevel(logging.INFO)
    logging.getLogger("listmodel").setLevel(logging.INFO)
    logging.getLogger("searcher").setLevel(logging.INFO)
    logging.getLogger("utils").setLevel(logging.INFO)
    logging.getLogger("memorybase").setLevel(logging.INFO)
    logging.getLogger("model").setLevel(logging.INFO)
    logging.getLogger("python").setLevel(logging.INFO)

    fname = sys.argv[1] # '/home/jal/Compil/python-haystack/test/dumps/cuckoo/1144-1.dmp'
    mapper = CuckooProcessMapper(fname)
    handler = mapper.make_memory_handler()
    finder = handler.get_heap_finder()
    heaps = finder.get_heap_mappings()
    print "heaps", heaps

    from haystack import api
    from haystack.allocators.win32.winxp_32 import struct__HEAP
    heap_constraints = finder._heap_module_constraints

    m = handler.get_mapping_for_address(0x00480000)
    res = api.load_record(handler, struct__HEAP, m.start, heap_constraints)
    logging.getLogger("basicmodel").setLevel(logging.DEBUG)
    v = api.validate_record(handler, res[0], heap_constraints)
    logging.getLogger("basicmodel").setLevel(logging.INFO)

    import code
    code.interact(local=locals())
    if len(heaps) == 0:

        # no heaps ??!!
        # it looks like 0x00030000 and other are..
        #DEBUG:basicmodel:ptr: Segments[1] <class 'haystack.types.LP_4_struct__HEAP_SEGMENT'> LP_4_struct__HEAP_SEGMENT(26083328) 0x18e0000 INVALID

        # explanation, not all mappings are dumped.
        # from https://github.com/cuckoosandbox/monitor/blob/master/bin/inject.c
        # (mbi.State & MEM_COMMIT) == 0 || (mbi.Protect & PAGE_GUARD) != 0 ||
        #            (mbi.Type & (MEM_IMAGE | MEM_MAPPED | MEM_PRIVATE)) == 0)
        #
        # when winappdbg does:
        # http://winappdbg.sourceforge.net/doc/v1.5/reference/winappdbg.win32.kernel32-pysrc.html#MemoryBasicInformation.has_content
        #    self.is_commited() and not bool(self.Protect & (PAGE_GUARD | PAGE_NOACCESS))
        #
        # a) But we do want private memory!!! And technically mem_mapped and mem_image would be nice.
        # b) It does not explain why the last mapping is truncated.

        # with the modified cuckoomon, it works better.
        # we are still missing the CriticalSection pointer mappings, which is probably a guard or something.
        # TODO -> change dump format to list all mappings, then data, with 0 data bytes if necessary.
        # TODO -> find why last mapping is truncated. Check WriteFile return value/written_bytes ?
        # maybe add debug statement to  cuckoo/analyzer/windows/lib/common/results.py upload_to_host ?
        # check bytes counts ?


        #m = handler.get_mappings()[0]
        #heap_constraints = finder._heap_module_constraints
        #logging.getLogger("basicmodel").setLevel(logging.DEBUG)
        #f._search_heap(h)

        possibles = []
        for m in handler.get_mappings():
            res = api.load_record(handler, struct__HEAP, m.start, heap_constraints)
            p, valid = api.output_to_python(handler, [res])[0]
            offset = m.offset
            print m, "p.Signature", valid, hex(p.Signature), repr(m._backend[8+offset:12+offset]),
            v = api.validate_record(handler, res[0], heap_constraints)
            print "validate", v
            if p.Signature == 0xeeffeeff:
                possibles.append(m)

        import code
        code.interact(local=locals())

        for m in possibles:
            print "trying m", m
            logging.getLogger("basicmodel").setLevel(logging.INFO)
            res = api.load_record(handler, struct__HEAP, m.start, heap_constraints)
            logging.getLogger("basicmodel").setLevel(logging.DEBUG)
            v = api.validate_record(handler, res[0], heap_constraints)
            print "that was", m
            import code
            code.interact(local=locals())

    else:

        from haystack.reverse import api
        api.reverse_instances(handler)

        import code
        code.interact(local=locals())


