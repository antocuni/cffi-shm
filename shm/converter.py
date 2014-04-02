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

class StringConverter(AbstractConverter):
    def to_python(self, cdata):
        cdata = self.ffi.cast('char*', cdata)
        return self.ffi.string(cdata)

    def from_python(self, s):
        return gclib.new_string(s)

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
