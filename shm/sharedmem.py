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

    def get_GC_malloc(self):
        raise NotImplementedError("Not available in read-only mode")
    
    get_GC_free = get_GC_malloc
    roots = property(get_GC_malloc)
    gc_disabled = property(get_GC_malloc)


sharedmem = Uninitialized_shm()
