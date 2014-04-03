from collections import defaultdict
import cffi
from shm import gclib

class AbstractConverter(object):
    def __init__(self, ffi, ctype):
        self.ffi = ffi
        self.ctype = ctype

    def to_python(self, cdata, force_cast=False):
        """
        Convert the given cdata into the corresponding Python object.  E.g.,
        <cdata char*> are converted into strings, <cdata long> into Python
        ints, and pointer to structs into their PyFFI equivalent.

        cdata is expected to be of the given ctype unless force_cast==True, in
        that case the proper cast will be performed.
        """
        if force_cast:
            cdata = self.ffi.cast(self.ctype, cdata)
        return self.to_python_impl(cdata)

    def to_python_impl(self, cdata):
        raise NotImplementedError

    def from_python(self, obj, ensure_shm=True):
        """
        Convert the given Python object into something which can be
        passed/stored as cdata. This includes the types which cffi handles
        automatically by itself: e.g., it is fine to return a Python string
        for a 'char*' ctype.

        If ensure_shm==True, make sure that the returned cdata lives in shared
        memory (and thus is it suitable to be e.g. stored in a struct.

        If ensure_shm==False, it means that the object is intended to be used
        only immediately, and only in address space of the current
        process. E.g., it is useful for doing dictionary lookups in slave
        processes, where you cannot call GC_malloc.
        """
        raise NotImplementedError


class Dummy(AbstractConverter):
    def to_python(self, cdata):
        return cdata

    def from_python(self, obj, ensure_shm=True):
        return obj

class StructPtr(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python_impl(self, cdata):
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True):
        return obj._ptr

class StructByVal(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python_impl(self, cdata):
        raise NotImplementedError('Cannot convert struct-by-val to python')

    def from_python(self, obj, ensure_shm=True):
        return obj._ptr
    

class String(AbstractConverter):
    def to_python_impl(self, cdata):
        return self.ffi.string(cdata)

    def from_python(self, s, ensure_shm=True):
        if ensure_shm:
            return gclib.new_string(s)
        else:
            return s

class ArrayOfChar(AbstractConverter):
    """
    Like StringConverter, but it does not need to GC-allocate a new string
    when converting from python, because the data will be copied anyway
    """
    def to_python(self, cdata):
        return self.ffi.string(cdata)

    def from_python(self, s, ensure_shm=True):
        return s


class Int(AbstractConverter):
    def to_python(self, cdata):
        return int(cdata)

    def from_python(self, obj, ensure_shm=True):
        return obj


# ==========================================================
# XXX: to be killed and integrated with pyffi.get_converter

_ffi = cffi.FFI()
_converter = defaultdict(lambda: Dummy)
_converter[_ffi.typeof('char*')] = String
_converter[_ffi.typeof('long')] = Int

def get_converter(ffi, t):
    ctype = ffi.typeof(t)
    cls = _converter[ctype]
    return cls(ffi, ctype)
