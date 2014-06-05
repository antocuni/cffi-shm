import os
from shm import gclib

class Uninitialized_shm(object):

    gclib = gclib
    path = None
    
    def init(self, path):
        self.gclib.init(path)
        self.path = path
        self.__class__ = RW_shm
    
    def open_readonly(self, path):
        self.gclib.open_readonly(path)
        self.path = path
        self.__class__ = RO_shm



class RW_shm(object):

    def init(self, path):
        if path == self.path:
            return
        raise ValueError('sharedmem already initialized: %s' % self.path)

    def open_readonly(self, path):
        raise ValueError('sharedmem already initialized in RW mode: %s' % self.path)

    new = staticmethod(gclib.new)
    new_array = staticmethod(gclib.new_array)
    realloc_array = staticmethod(gclib.realloc_array)
    gc_disabled = gclib.disabled
    get_GC_malloc = gclib.lib.get_GC_malloc
    get_GC_free = gclib.lib.get_GC_free
    roots = gclib.roots



class RO_shm(object):

    def init(self, path):
        raise ValueError('sharedmem already opened in RO mode: %s' % self.path)

    def open_readonly(self, path):
        if path == self.path:
            return
        raise ValueError('sharedmem already opened: %s' % self.path)

    def _not_implemented(self, *args, **kwargs):
        raise NotImplementedError("Not available in read-only mode")

    new = _not_implemented
    new_array = _not_implemented
    realloc_array = _not_implemented
    gc_disabled = property(_not_implemented)
    get_GC_malloc = _not_implemented
    get_GC_free = _not_implemented
    roots = property(_not_implemented)


sharedmem = Uninitialized_shm()
