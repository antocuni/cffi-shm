from collections import defaultdict
import cffi
from shm import gclib

class AbstractConverter(object):
    def __init__(self, ffi, ctype):
        self.ffi = ffi
        self.ctype = ctype

class DummyConverter(AbstractConverter):
    def to_python(self, cdata):
        return cdata

    def from_python(self, obj):
        return obj

class StructConverter(AbstractConverter):
    def __init__(self, ffi, ctype, class_):
        AbstractConverter.__init__(self, ffi, ctype)
        self.class_ = class_

    def to_python(self, cdata):
        return self.class_.from_pointer(cdata)

    def from_python(self, obj):
        return obj._ptr


class StringConverter(AbstractConverter):
    def to_python(self, cdata):
        cdata = self.ffi.cast('char*', cdata) # XXX: integrate with 'force_cast'
        return self.ffi.string(cdata)

    def from_python(self, s):
        return gclib.new_string(s)

class ArrayOfCharsConverter(AbstractConverter):
    """
    Like StringConverter, but it does not need to GC-allocate a new string
    when converting from python, because the data will be copied anyway
    """
    def to_python(self, cdata):
        return self.ffi.string(cdata)

    def from_python(self, s):
        return s


class IntConverter(AbstractConverter):
    def to_python(self, cdata):
        return int(cdata)

    def from_python(self, obj):
        return obj


# ==========================================================
# XXX: to be killed and integrated with pyffi.get_converter

_ffi = cffi.FFI()
_converter = defaultdict(lambda: DummyConverter)
_converter[_ffi.typeof('char*')] = StringConverter
_converter[_ffi.typeof('long')] = IntConverter

def get_converter(ffi, t):
    ctype = ffi.typeof(t)
    cls = _converter[ctype]
    return cls(ffi, ctype)
