from shm.struct import StructDecorator
from shm.util import cffi_typeof

class PyFFI(object):
    def __init__(self, ffi):
        self.ffi = ffi
        self.pytypes = {} # ctype --> python class

    def pytypeof(self, t):
        ctype = cffi_typeof(self.ffi, t)
        return self.pytypes[ctype]

    def register(self, t, pytype):
        ctype = cffi_typeof(self.ffi, t)
        self.pytypes[ctype] = pytype

    def struct(self, t, **kwds):
        ctype = cffi_typeof(self.ffi, t)
        return StructDecorator(self, ctype, **kwds)
