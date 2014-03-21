from collections import defaultdict
import cffi
from shm import gclib

class DummyConverter(object):
    @staticmethod
    def to_python(ffi, cdata):
        return cdata

    @staticmethod
    def from_python(ffi, obj):
        return obj

class StrConverter(object):
    @staticmethod
    def to_python(ffi, cdata):
        cdata = ffi.cast('char*', cdata)
        return ffi.string(cdata)

    @staticmethod
    def from_python(ffi, s):
        return gclib.new_string(s)

class IntConverter(object):
    @staticmethod
    def to_python(ffi, cdata):
        return int(cdata)

    @staticmethod
    def from_python(ffi, obj):
        return obj

_ffi = cffi.FFI()
_converter = defaultdict(lambda: DummyConverter)
_converter[_ffi.typeof('char*')] = StrConverter
_converter[_ffi.typeof('long')] = IntConverter

def get_converter(ffi, typ):
    ctype = ffi.typeof(typ)
    return _converter[ctype]
