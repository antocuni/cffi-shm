from collections import defaultdict
import cffi
from shm import gclib
from shm.util import ctype_pointer_to, ctype_array_of

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
        if cdata == self.ffi.NULL:
            return None
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True):
        if obj is None:
            return self.ffi.NULL
        return obj.as_cdata()

class StructByVal(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    # note that here we override directly to_python, not to_python_impl
    def to_python(self, cdata, force_cast=False):
        if force_cast:
            ctype_ptr = ctype_pointer_to(self.ffi, self.ctype)
            cdata = self.ffi.cast(ctype_ptr, cdata)
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True):
        return obj.as_cdata()


class GenericTypePtr(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python_impl(self, cdata):
        if cdata == self.ffi.NULL:
            return None
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True):
        if obj is None:
            return self.ffi.NULL
        # obj.as_cdata returns the concrete type (e.g. List* from listffi),
        # but we need to cast it to the corresponding opaque generic type
        return self.ffi.cast(self.ctype, obj.as_cdata())


class String(AbstractConverter):
    def to_python_impl(self, cdata):
        if cdata == self.ffi.NULL:
            return None
        return self.ffi.string(cdata)

    def from_python(self, s, ensure_shm=True):
        if s is None:
            return self.ffi.NULL
        if ensure_shm:
            return gclib.new_string(s)
        else:
            return s

class ArrayOfChar(AbstractConverter):
    """
    Like StringConverter, but it does not need to GC-allocate a new string
    when converting from python, because the data will be copied anyway
    """
    def to_python_impl(self, cdata):
        return self.ffi.string(cdata)

    def from_python(self, s, ensure_shm=True):
        return s

class Primitive(AbstractConverter):
    """
    cffi already knows how to convert primitive cdata to Python objects,
    e.g. by converting 'long' to Python ints and 'double' to Python floats.

    However, it does not offert a direct API to do the conversion, so instead
    we store to a buffer and read them again.
    """

    def __init__(self, ffi, ctype):
        AbstractConverter.__init__(self, ffi, ctype)
        array_type = ctype_array_of(ffi, ctype)
        self.buf = ffi.new(array_type, 1)

    def to_python_impl(self, cdata):
        self.buf[0] = cdata
        return self.buf[0]

    def from_python(self, obj, ensure_shm=True):
        return obj

class DoubleOrNone(AbstractConverter):
    """
    Convert Python floats to and from C doubles.
    Python None is converted to NaN.

    This converter is never used by default, it must be explicitly passed as a
    custom converter.
    """

    def to_python_impl(self, cdata):
        value = float(cdata)
        if value != value: # NaN:
            return None
        return value

    def from_python(self, obj, ensure_shm=True):
        if obj is None:
            return float('NaN')
        return obj
