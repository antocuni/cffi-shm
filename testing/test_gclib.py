import cffi
from shm import gclib
gclib.init('/run/shm/cffi-shm-testing')

ffi = cffi.FFI()
ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;
""")

def test_new():
    gclib.roots.reinit()
    gclib.collect()
    gclib.collect()
    p1 = gclib.new(ffi, 'Point')
    assert ffi.typeof(p1) is ffi.typeof('Point*')
    gclib.collect()
    p2 = gclib.new(ffi, 'Point')
    # the GC does not know about any root yet, so it collects p1, and it
    # allocates p2 at the same address as p1
    assert p1 == p2

def test_new_root():
    gclib.roots.reinit()
    gclib.collect()
    gclib.collect()
    p1 = gclib.new(ffi, 'Point', root=True)
    gclib.collect()
    p2 = gclib.new(ffi, 'Point')
    assert p1 != p2

def test_new_array():
    arr = gclib.new_array(ffi, 'Point', 10)
    assert ffi.typeof(arr) is ffi.typeof('Point[10]')
    assert ffi.sizeof(arr) == 10 * ffi.sizeof('Point')

def test_new_string():
    ptr = gclib.new_string('hello')
    assert ptr[0] == 'h'
    assert ptr[4] == 'o'
    assert ptr[5] == '\0'
    assert ffi.string(ptr) == 'hello'

def allocate_many(n=10000):
    a = gclib.total_collections()
    for i in range(n):
        p = gclib.new(ffi, 'Point')
    b = gclib.total_collections()
    return a, b
    
def test_gc_enabled():
    # we check that with the GC enabled, after a while it collects and we
    # start allocating at lower addresses (remember that by default the result
    # of new() is not a root)
    a, b = allocate_many()
    assert b > a

def test_gc_disabled():
    gclib.collect()
    with gclib.disabled:
        a, b = allocate_many()
        assert a == b
    a, b = allocate_many()
    assert b > a
