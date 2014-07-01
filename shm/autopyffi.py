from shm.pyffi import PyFFI

class AutoPyFFI(PyFFI):
    def __init__(self, *args, **kwds):
        PyFFI.__init__(self, *args, **kwds)
        
        class ImmutableStruct(object):
            __metaclass__ = MetaStruct
            pyffi = self
            immutable = True

        class Struct(object):
            __metaclass__ = MetaStruct
            pyffi = self
            immutable = False

        self.ImmutableStruct = ImmutableStruct
        self.Struct = Struct


class MetaStruct(type):
    def __new__(metacls, name, bases, dic):
        if bases == (object,):
            # this is ImmutableStruct or Struct, no need to do anything
            return type.__new__(metacls, name, bases, dic)
        #
        # this is a proper subclass, do the magic
        if len(bases) > 1:
            raise TypeError, 'Multiple inheritance not supported'
        base = bases[0]
        pyffi = base.pyffi
        pyffi.ffi.cdef(dic['__doc__'])
        basestruct = pyffi.struct(name, immutable=base.immutable)
        return type(name, (basestruct,), dic)
