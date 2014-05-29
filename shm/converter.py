import sys
import time
import datetime
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

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        """
        Convert the given Python object into something which can be
        passed/stored as cdata. This includes the types which cffi handles
        automatically by itself: e.g., it is fine to return a Python string
        for a 'char*' ctype.

        If ensure_shm==True, make sure that the returned cdata lives in shared
        memory (and thus is it suitable to be e.g. stored in a struct).

        If ensure_shm==False, it means that the object is intended to be used
        only immediately, and only in address space of the current
        process. E.g., it is useful for doing dictionary lookups in slave
        processes, where you cannot call GC_malloc.

        If as_voidp==True, return something which can be passed to a function
        expecting a void*. E.g., for primitive types a cast to void* is
        necessary, but e.g. for strings it is done automatically (and moreover
        strings cannot be explicitly casted to void*). Note that for all
        converters which already returns a pointer, the cast is not necessary
        as pointers are always convertible to void* anyway.
        """
        raise NotImplementedError

    def _as_voidp_maybe(self, obj, as_voidp):
        if as_voidp:
            return self.ffi.cast('void*', obj)
        return obj


class Dummy(AbstractConverter):
    def to_python(self, cdata):
        return cdata

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        return obj


class StructPtr(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python_impl(self, cdata):
        if cdata == self.ffi.NULL:
            return None
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
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

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        return obj.as_cdata()


class GenericTypePtr(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python_impl(self, cdata):
        if cdata == self.ffi.NULL:
            return None
        return self.class_.from_pointer(cdata)

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
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

    def from_python(self, s, ensure_shm=True, as_voidp=False):
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

    def from_python(self, s, ensure_shm=True, as_voidp=False):
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

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        return self._as_voidp_maybe(obj, as_voidp)

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

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        if obj is None:
            obj = float('NaN')
        return self._as_voidp_maybe(obj, as_voidp)

class LongOrNone(AbstractConverter):
    """
    Convert Python ints to and from C longs.
    -sys.maxint-1 is converted to None

    This converter is never used by default, it must be explicitly passed as a
    custom converter.
    """

    sentinel = -sys.maxint-1

    def to_python_impl(self, cdata):
        value = int(cdata)
        if value == self.sentinel:
            return None
        return value

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        if obj is None:
            obj = self.sentinel
        return self._as_voidp_maybe(obj, as_voidp)


class DateTimeConverter(AbstractConverter):
    """
    Convert Python datetime objects to and from C doubles.
    """
    type = datetime.datetime

    def to_python_impl(self, cdata):
        value = float(cdata)
        if value != value: # NaN:
            return None
        return self.type.fromtimestamp(value)

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        if obj is None:
            value = float('NaN')
        else:
            value = time.mktime(obj.timetuple())
        return self._as_voidp_maybe(value, as_voidp)


class DateConverter(DateTimeConverter):
    """
    Convert Python date objects to and from C doubles.
    """
    type = datetime.date


class TimeConverter(AbstractConverter):
    """
    Convert Python datetime.time() to and from C longs. It is stored as the
    number of seconds from midnight. Note that microseconds are lost.
    """

    sentinel = -sys.maxint-1

    def to_python_impl(self, cdata):
        value = int(cdata)
        if value == self.sentinel:
            return None
        hhmm, ss = divmod(value, 60)
        hh, mm = divmod(hhmm, 60)
        return datetime.time(hh, mm, ss)

    def from_python(self, obj, ensure_shm=True, as_voidp=False):
        if obj is None:
            value = self.sentinel
        else:
            value = obj.hour*3600 + obj.minute*60 + obj.second
        return self._as_voidp_maybe(value, as_voidp)
