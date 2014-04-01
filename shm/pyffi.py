from shm.struct import StructDecorator

class PyFFI(object):
    def __init__(self, ffi):
        self.ffi = ffi
        self.pytypes = {} # ctype --> python class

    def ctypeof(self, ctype):
        if isinstance(ctype, str):
            return self.ffi.typeof(ctype)
        return ctype

    def pytypeof(self, ctype):
        ctype = self.ctypeof(ctype)
        return self.pytypes[ctype]

    def register(self, ctype, pytype):
        ctype = self.ctypeof(ctype)
        self.pytypes[ctype] = pytype

    def struct(self, ctype, **kwds):
        ctype = self.ctypeof(ctype)
        return StructDecorator(self, ctype, **kwds)
