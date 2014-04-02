from shm.struct import StructDecorator
from shm import converter
from shm.util import (cffi_typeof, cffi_is_struct_ptr, cffi_is_string,
                      cffi_is_char_array, compile_def, identity)


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
        # XXX
        if cffi_is_struct_ptr(self.ffi, ctype):
            self.pytypes[ctype.item] = pytype

    def struct(self, t, **kwds):
        ctype = cffi_typeof(self.ffi, t)
        return StructDecorator(self, ctype, **kwds)

    def get_converter(self, t, allow_structs_byval=False):
        ctype = cffi_typeof(self.ffi, t)
        if cffi_is_struct_ptr(self.ffi, ctype):
            cls = self.pytypeof(t)
            return converter.StructPtr(self.ffi, ctype, cls)
        elif ctype.kind == 'struct':
            if not allow_structs_byval:
                msg = ("structs byval are not allowed by default. You need to use a "
                       "pointer to a struct, or specify allow_structs_byval=True")
                raise ValueError(msg)
            cls = self.pytypeof(t)
            return converter.StructByVal(self.ffi, ctype, cls)
        if cffi_is_string(self.ffi, ctype):
            return converter.String(self.ffi, ctype)
        elif cffi_is_char_array(self.ffi, t):
            return converter.ArrayOfChar(self.ffi, ctype)
        elif ctype == self.ffi.typeof('long'):
            # XXX: this must be converted into a more general PrimitiveConverter
            return converter.Int(self.ffi, ctype)
        else:
            return converter.Dummy(self.ffi, ctype)