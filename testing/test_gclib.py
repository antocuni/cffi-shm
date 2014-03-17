import cffi
from shm import gclib

ffi = cffi.FFI()
ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;
""")

def test_new():
    gclib.init('/run/shm/cffi-shm-testing')
    p1 = gclib.new(ffi, 'Point')
    assert ffi.typeof(p1) is ffi.typeof('Point*')
    gclib.collect()
    p2 = gclib.new(ffi, 'Point')
    # the GC does not know about any root yet, so it collects p1, and it
    # allocates p2 at the same address as p1
    assert p1 == p2

