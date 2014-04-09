import py
import cffi
from shm import gclib
from shm.pyffi import PyFFI
gclib.init('/cffi-shm-testing')

def test_register():
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    class A(object):
        pass
    class B(object):
        pass
    class SubA(A):
        pass

    pyffi.register('long', A)
    assert pyffi.pytypeof('long') is A
    py.test.raises(TypeError, "pyffi.register('long', B)")
    pyffi.register('long', SubA)
    assert pyffi.pytypeof('long') is SubA

def test_register_list():
    from shm.list import ListType
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    LT = pyffi.list('long')
    assert isinstance(LT, ListType)
    #
    LT = pyffi.list('long', cname='LongList')
    assert pyffi.pytypeof('LongList*') is LT

def test_register_dict():
    from shm.dict import DictType
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    DT = pyffi.dict('const char*', 'long')
    assert isinstance(DT, DictType)
    
    DT = pyffi.dict('const char*', 'long', cname='MyDict')
    assert pyffi.pytypeof('MyDict*') is DT


def test_StructConverter():
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct {
            int x;
            int y;
        } Point;
    """)
    
    pyffi = PyFFI(ffi)
    Point = pyffi.struct('Point')

    conv = pyffi.get_converter('Point*')
    p = Point(1, 2)
    assert conv.from_python(p) is p._ptr
    p2 = conv.to_python(p._ptr)
    assert isinstance(p2, Point)
    assert p2 is not p
    assert p2._ptr is p._ptr
    #
    assert conv.from_python(None) == ffi.NULL
    assert conv.to_python(ffi.NULL) is None

def test_StringConverter():
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    conv = pyffi.get_converter('const char*')
    p = conv.from_python('hello')
    assert ffi.typeof(p) == ffi.typeof('char*')
    assert ffi.string(p) == 'hello'
    assert gclib.isptr(p)
    #
    s2 = conv.from_python('hello', ensure_shm=False)
    assert type(s2) is str
    assert s2 == 'hello'
    #
    p2 = ffi.new('char[]', 'foobar')
    assert conv.to_python(p2) == 'foobar'
    #
    assert conv.from_python(None) == ffi.NULL
    assert conv.to_python(ffi.NULL) is None
    

def test_PrimitiveConverter():
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    conv = pyffi.get_converter('long')
    cdata = ffi.cast('long', 42)
    obj = conv.to_python(cdata)
    assert type(obj) is int
    
def test_cache_converter():
    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    a = pyffi.get_converter('long')
    b = pyffi.get_converter('long')
    c = pyffi.get_converter('long', allow_structs_byval=True)
    assert a is b is c
