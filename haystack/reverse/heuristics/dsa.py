#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Loic Jaquemet loic.jaquemet+python@gmail.com
#

import logging
import os
import array
import struct
import itertools

from haystack.config import Config
from haystack.utils import unpackWord
from haystack.reverse import re_string, fieldtypes
from haystack.reverse.fieldtypes import FieldType, Field
from haystack.reverse.heuristics.model import FieldAnalyser, StructureAnalyser

import ctypes

log = logging.getLogger('dsa')

## Field analysis related functions and classes

class ZeroFields(FieldAnalyser):
  ''' checks for possible fields, aligned, with WORDSIZE zeros.'''
  def make_fields(self, structure, offset, size):
    assert( offset%Config.WORDSIZE == 0 ) #vaddr and offset should be aligned
    #log.debug('checking Zeroes')
    self._typename = FieldType.ZEROES
    self._zeroes = '\x00'*Config.WORDSIZE

    ret = self._find_zeroes(structure, offset, size)
    
    # TODO if its just a word, we should say its a small int.
    return ret  
  
  def _find_zeroes(self, structure, offset, size):
    ''' iterate over the bytes until a byte if not \x00 
    '''
    bytes = structure.bytes
    #print 'offset:%x blen:%d'%(offset, len(bytes))
    #print repr(bytes)
    assert( (offset)%Config.WORDSIZE == 0 )
    #aligned_off = (offset)%Config.WORDSIZE 
    start = offset
    #if aligned_off != 0: # align to next
    #  start += (Config.WORDSIZE - aligned_off)
    #  size  -= (Config.WORDSIZE - aligned_off)
    # iterate
    matches = array.array('i')
    for i in range(start, start+size, Config.WORDSIZE ):
      # PERF TODO: bytes or struct test ?
      #print repr(bytes[start+i:start+i+Config.WORDSIZE])
      if bytes[start+i:start+i+Config.WORDSIZE] == self._zeroes:
        matches.append(start+i)
        #print matches
    # collate
    if len(matches) == 0:
      return []
    # lets try to get fields
    fields = []
    # first we need to collate neighbors
    collates = list()
    prev = matches[0]-Config.WORDSIZE
    x = []
    # PERF TODO: whats is algo here
    for i in matches:
      if i-Config.WORDSIZE == prev:
        x.append(i)
      else:
        collates.append(x)
        x = [i]
      prev = i
    collates.append(x)
    #log.debug(collates)
    # we now have collated, lets create fields
    for field in collates:
      flen = len(field)
      if flen > 1:
        size = Config.WORDSIZE * flen
      elif flen == 1:
        size = Config.WORDSIZE
      else:
        continue
      # make a field
      fields.append( Field(structure, start+field[0], self._typename, size, False) ) 
    # we have all fields
    return fields

class UTF16Fields(FieldAnalyser):
  ''' rfinds utf-16-ascii and ascii 7bit
  
  '''
  def make_fields(self, structure, offset, size):
    assert( offset%Config.WORDSIZE == 0 ) #vaddr and offset should be aligned
    #log.debug('checking String')
    fields = []
    bytes = structure.bytes
    while size > Config.WORDSIZE:
      #print 're_string.rfind_utf16(bytes, %d, %d)'%(offset,size)
      index = re_string.rfind_utf16(bytes, offset, size)
      if index > -1:
        f = Field(structure, offset+index, FieldType.STRING16, size-index, False)  
        #print repr(structure.bytes[f.offset:f.offset+f.size])
        fields.append(f)
        size = index # reduce unknown field in prefix
      else:
        size -= Config.WORDSIZE # reduce unkown field
    # look in head
    return fields
  
class PrintableAsciiFields(FieldAnalyser):
  ''' finds printable ascii fields '''
  def make_fields(self, structure, offset, size):
    assert( offset%Config.WORDSIZE == 0 ) #vaddr and offset should be aligned
    #log.debug('checking String')
    fields = []
    bytes = structure.bytes
    while size > Config.WORDSIZE:
      #print 're_string.find_ascii(bytes, %d, %d)'%(offset,size)
      index, ssize = re_string.find_ascii(bytes, offset, size)
      if index == 0:
        if (ssize < size) and bytes[offset+index+ssize]=='\x00': # space for a \x00
          ssize +=1
          f = Field(structure, offset+index, FieldType.STRINGNULL, ssize, False)  
        else:
          f = Field(structure, offset+index, FieldType.STRING, ssize, False)  
        #print repr(structure.bytes[f.offset:f.offset+f.size])
        fields.append(f)
        size -= ssize # reduce unknown field 
      else:
        size -= Config.WORDSIZE # reduce unkown field
    # look in head
    return fields
  


class PointerFields(FieldAnalyser):
  ''' TODO tests '''
  ''' looks at a word for a pointer value'''
  def make_fields(self, structure, offset, size):
    # iterate on all offsets . NOT assert( size == Config.WORDSIZE)
    assert( offset%Config.WORDSIZE == 0 ) #vaddr and offset should be aligned
    log.debug('checking Pointer')
    bytes = structure.bytes
    fields = []
    while size >= Config.WORDSIZE:
      value = unpackWord(bytes[offset:offset+Config.WORDSIZE])
      # check if pointer value is in range of mappings and set self.comment to pathname value of pointer
      # TODO : if bytes 1 & 3 == \x00, maybe utf16 string
      if value not in structure._mappings:
        size -= Config.WORDSIZE
        offset += Config.WORDSIZE
        continue
      # we have a pointer
      log.debug('checkPointer offset:%s value:%s'%(offset, hex(value)))
      field = Field(structure, offset, FieldType.POINTER, Config.WORDSIZE, False)  
      field.value = value
      # TODO: leverage the context._function_names 
      if value in structure._context._function_names :
        field.comment = ' %s::%s'%(os.path.basename(structure._mappings.getMmapForAddr(value).pathname), 
                    structure._context._function_names[value])
      else:
        field.comment = structure._mappings.getMmapForAddr(value).pathname 
      fields.append(field)
      size -= Config.WORDSIZE
      offset += Config.WORDSIZE
    return fields



class IntegerFields(FieldAnalyser):
  ''' looks at a word for a small int value'''
  def make_fields(self, structure, offset, size):
    # iterate on all offsets . NOT assert( size == Config.WORDSIZE)
    assert( offset%Config.WORDSIZE == 0 ) #vaddr and offset should be aligned
    #log.debug('checking Integer')
    bytes = structure.bytes
    fields = []
    while size >= Config.WORDSIZE:
      #print 'checking >'
      field = self.checkSmallInt(structure, bytes, offset)
      if field is None:
        #print 'checking <'
        field = self.checkSmallInt(structure, bytes, offset, '>')
      # we have a field smallint
      if field is not None:
        fields.append(field)      
      size -= Config.WORDSIZE
      offset += Config.WORDSIZE
    return fields

  def checkSmallInt(self, structure, bytes, offset, endianess='<'):
    ''' check for small value in signed and unsigned forms '''
    val = unpackWord(bytes[offset:offset+Config.WORDSIZE], endianess)
    #print endianess, val
    if val < 0xffff:
      field = Field(structure, offset, FieldType.SMALLINT, Config.WORDSIZE, False)
      field.value = val
      field.endianess = endianess
      return field
    elif ( (2**(Config.WORDSIZE*8) - 0xffff) < val): # check signed int
      field = Field(structure, offset, FieldType.SIGNED_SMALLINT, Config.WORDSIZE, False)
      field.value = val
      field.endianess = endianess
      return field
    return None


class DSASimple(StructureAnalyser):
  zero_a = ZeroFields()
  ascii_a = PrintableAsciiFields()
  utf16_a = UTF16Fields()
  int_a = IntegerFields()
  ptr_a = PointerFields()

  def analyze_fields(self, structure):
    structure.reset()
    fields, gaps = self._analyze(structure)
    structure.add_fields(fields)
    structure.add_fields(gaps) #, FieldType.UNKNOWN
    structure.resolved = True
    return structure
    
  def _analyze(self, structure):
    slen = len(structure)
    offset = 0
    # call on analyzers
    fields = []
    nb = -1
    gaps = [Field( structure, 0, FieldType.UNKNOWN, len(structure), False)]
    
    # find zeroes
    # find strings
    # find smallints
    # find pointers
    for analyser in [ self.zero_a, self.utf16_a, self.ascii_a, self.int_a, self.ptr_a]:
      for field in gaps:
        if field.padding:
          fields.append(field)
          continue
        log.debug('Using %s on %d:%d'%(analyser.__class__.__name__, field.offset, field.offset+len(field)))
        fields.extend( analyser.make_fields(structure, field.offset, len(field)) )
        #print fields
      if len(fields) != nb: # no change in fields, keep gaps
        nb = len(fields)
        gaps = self._make_gaps(structure, fields)
      if len(gaps) == 0:
        return fields, gaps
    return fields, gaps

  def _make_gaps(self, structure, fields):
    fields.sort()
    gaps = []
    nextoffset = 0
    for i, f in enumerate(fields):
      if f.offset > nextoffset : # add temp padding field
        if nextoffset%Config.WORDSIZE == 0:
          gap = Field( structure, nextoffset, FieldType.UNKNOWN, f.offset-nextoffset, False)
          log.debug('_make_gaps: adding field at offset %d:%d'%(gap.offset, gap.offset+len(gap) ))
          gaps.append(gap)
        else:   # unaligned field should be splitted
          s1 = Config.WORDSIZE - nextoffset%Config.WORDSIZE
          gap1 = Field( structure, nextoffset, FieldType.UNKNOWN, s1, True)
          gap2 = Field( structure, nextoffset+s1, FieldType.UNKNOWN, f.offset-nextoffset-s1, False)
          log.debug('_make_gaps: Unaligned field at offset %d:%d'%(gap1.offset, gap1.offset+len(gap1) ))
          log.debug('_make_gaps: adding field at offset %d:%d'%(gap2.offset, gap2.offset+len(gap2) ))
          gaps.append(gap1)
          gaps.append(gap2)
      elif f.offset < nextoffset :
        assert(f.offset >= nextoffset) # No overlaps authorised
      # do next field
      nextoffset = f.offset + len(f)
    # conclude on QUEUE insertion
    lastfield_size = len(structure)-nextoffset
    if lastfield_size > 0 :
      if lastfield_size < Config.WORDSIZE:
        gap = Field( structure, nextoffset, FieldType.UNKNOWN, lastfield_size, True)
      else:
        gap = Field( structure, nextoffset, FieldType.UNKNOWN, lastfield_size, False)
      log.debug('_make_gaps: adding last field at offset %d:%d'%(gap.offset, gap.offset+len(gap) ))
      gaps.append(gap)
    return gaps
  

class IntegerArrayFields(StructureAnalyser):
  ''' TODO '''
  def make_fields(self, structure, offset, size):
    # this should be last resort
    bytes = self.struct.bytes[self.offset:self.offset+self.size]
    size = len(bytes)
    if size < 4:
      return False
    ctr = collections.Counter([ bytes[i:i+Config.WORDSIZE] for i in range(len(bytes)) ] )
    floor = max(1,int(size*.1)) # 10 % variation in values
    #commons = [ c for c,nb in ctr.most_common() if nb > 2 ]
    commons = ctr.most_common()
    if len(commons) > floor:
      return False # too many different values
    # few values. it migth be an array
    self.size = size
    self.values = bytes
    self.comment = '10%% var in values: %s'%(','.join([ repr(v) for v,nb in commons]))
    return True
        
    

