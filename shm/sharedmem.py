import os
import cffi
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
    new_string = staticmethod(gclib.new_string)
    realloc_array = staticmethod(gclib.realloc_array)
    gc_disabled = gclib.disabled
    get_GC_malloc = gclib.lib.get_GC_malloc
    get_GC_free = gclib.lib.get_GC_free
    roots = gclib.roots

    def protect(self):
        """
        Protect the shared memory against writing. It is still possible to
        read it.
        """
        gclib.protect_GC_memory(gclib.lib.PROT_READ)

    def unprotect(self):
        """
        Undo the effect of protect. The GC memory is turned Read/Write again.
        """
        gclib.protect_GC_memory(gclib.lib.PROT_READ | gclib.lib.PROT_WRITE)


class DummyContextManager(object):
    def __enter__(self):
        pass

    def __exit__(self, exc, exctype, tb):
        pass

class RO_shm(object):

    ffi = cffi.FFI()
    ffi.cdef("""
        void free(void* ptr);
    """)
    lib = ffi.verify("#include <stdlib.h>")

    def init(self, path):
        raise ValueError('sharedmem already opened in RO mode: %s' % self.path)

    def open_readonly(self, path):
        if path == self.path:
            return
        raise ValueError('sharedmem already opened: %s' % self.path)

    def _not_implemented(self, *args, **kwargs):
        raise NotImplementedError("Not available in read-only mode")

    new_array = _not_implemented
    realloc_array = _not_implemented
    get_GC_malloc = _not_implemented
    get_GC_free = _not_implemented
    roots = property(_not_implemented)

    # XXX: __keepalive is never shrinked, so we are leaking memory right now :-(
    __keepalive = []
    
    def new(self, ffi, t, root=True):
        ptr = ffi.new(t)
        self.__keepalive.append(ptr)
        return ptr

    def new_string(self, s, root=True):
        ptr = self.ffi.new('char[]', s)
        self.__keepalive.append(ptr)
        return ptr

    def new_array(self, ffi, t, n, root=True):
        ptr = ffi.new(t+'[]', n)
        self.__keepalive.append(ptr)
        return ptr

    gc_disabled = DummyContextManager()

    def protect(self):
        """
        Protect the shared memory against reading or writing.
        """
        gclib.protect_GC_memory(gclib.lib.PROT_NONE)

    def unprotect(self):
        """
        Undo the effect of protect. The GC memory is turned Read-only again.
        """
        gclib.protect_GC_memory(gclib.lib.PROT_READ)


sharedmem = Uninitialized_shm()
