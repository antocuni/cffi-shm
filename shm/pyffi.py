from shm.struct import make_struct
from shm import converter
from shm.util import (cffi_typeof, cffi_is_struct_ptr, cffi_is_string,
                      cffi_is_char_array, compile_def, identity)

class AbstractGenericType(object):
    pass


class PyFFI(object):
    def __init__(self, ffi):
        self.ffi = ffi
        self.pytypes = {} # ctype --> python class
        self._converters = {}

    def pytypeof(self, t):
        ctype = cffi_typeof(self.ffi, t)
        return self.pytypes[ctype]

    def register(self, t, pytype):
        ctype = cffi_typeof(self.ffi, t)
        cur_pytype = self.pytypes.get(ctype)
        if cur_pytype is not None:
            if not issubclass(pytype, cur_pytype):
                raise TypeError("The wrapper class for ctype %s has already "
                                "been registered as %s" % (t, self.pytypes[ctype]))
        self.pytypes[ctype] = pytype

    def struct(self, t, **kwds):
        ctype = cffi_typeof(self.ffi, t)
        cls = make_struct(self, ctype, **kwds)
        return cls

    def list(self, t, cname=None, **kwds):
        from shm.list import ListType
        LT = ListType(self, t, **kwds)
        if cname:
            self._new_opaque_type(cname)
            self.register(cname+'*', LT)
        return LT

    def dict(self, keytype, valuetype, cname=None, **kwds):
        from shm.dict import DictType
        DT = DictType(self, keytype, valuetype, **kwds)
        if cname:
            self._new_opaque_type(cname)
            self.register(cname+'*', DT)
        return DT

    def _new_opaque_type(self, t):
        self.ffi.cdef('typedef struct %s %s;' % (t, t))

    def get_converter(self, t, allow_structs_byval=False):
        ctype = cffi_typeof(self.ffi, t)
        if ctype.kind == 'struct':
            key = (ctype, allow_structs_byval)
        else:
            key = (ctype,)
        try:
            return self._converters[key]
        except KeyError:
            conv = self._new_converter(ctype, allow_structs_byval)
            self._converters[key] = conv
            return conv

    def _new_converter(self, ctype, allow_structs_byval):
        if cffi_is_struct_ptr(self.ffi, ctype):
            cls = self.pytypeof(ctype)
            if isinstance(cls, AbstractGenericType):
                return converter.GenericTypePtr(self.ffi, ctype, cls)
            else:
                return converter.StructPtr(self.ffi, ctype, cls)
        elif ctype.kind == 'struct':
            if not allow_structs_byval:
                msg = ("structs byval are not allowed by default. You need to use a "
                       "pointer to a struct, or specify allow_structs_byval=True")
                raise ValueError(msg)
            cls = self.pytypeof(ctype)
            return converter.StructByVal(self.ffi, ctype, cls)
        if cffi_is_string(self.ffi, ctype):
            return converter.String(self.ffi, ctype)
        elif cffi_is_char_array(self.ffi, ctype):
            return converter.ArrayOfChar(self.ffi, ctype)
        elif ctype.kind == 'primitive':
            return converter.Primitive(self.ffi, ctype)
        else:
            return converter.Dummy(self.ffi, ctype)

