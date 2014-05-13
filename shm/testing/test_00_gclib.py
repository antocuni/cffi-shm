import cffi
from shm import gclib
gclib.init('/cffi-shm-testing')

ffi = cffi.FFI()
ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;
""")

def test_gc_memory():
    gb = 1024**3
    assert gclib.lib.GC_get_memory() == ffi.cast('void*', 0x1000000000)
    assert gclib.lib.GC_get_memsize() == 4*gb * 768

def test_new():
    gclib.roots.reinit()
    gclib.collect()
    gclib.collect()
    p1 = gclib.new(ffi, 'Point*', root=False)
    assert gclib.isptr(p1)
    assert ffi.typeof(p1) is ffi.typeof('Point*')
    gclib.collect()
    p2 = gclib.new(ffi, 'Point*', root=False)
    # the GC does not know about any root yet, so it collects p1, and it
    # allocates p2 at the same address as p1
    assert p1 == p2

def test_new_root():
    gclib.roots.reinit()
    gclib.collect()
    gclib.collect()
    p1 = gclib.new(ffi, 'Point*')
    gclib.collect()
    p2 = gclib.new(ffi, 'Point*', root=False)
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
        p = gclib.new(ffi, 'Point*', root=False)
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


def test_register_roots():
    roots = gclib.GcRootCollection()
    ptr = gclib.gcffi.cast('void*', 0x42)
    a = roots._add(ptr)
    assert a.i == 0
    assert roots.mem[0] == ptr
    #
    b = roots._add(ptr)
    assert b.i == 1
    assert roots.mem[1] == ptr
    #
    a.clear(ptr)
    assert roots.mem[0] == gclib.gcffi.NULL
    assert roots.mem[1] == ptr


def test_root_keepalive():
    import gc
    def getaddr(ptr):
        return int(ffi.cast('long', ptr))

    gclib.collect()
    #
    ptr1 = gclib.new(ffi, 'Point*')
    addr1 = getaddr(ptr1)
    gclib.collect() # note that this is gclib's collect
    ptr2 = gclib.new(ffi, 'Point*')
    addr2 = getaddr(ptr2)
    assert addr1 != addr2
    #
    ptr1 = None
    ptr2 = None
    gc.collect(); gc.collect(); gc.collect(); # this is Python's collect
    gclib.collect()
    ptr3 = gclib.new(ffi, 'Point*')
    addr3 = getaddr(ptr3)
    assert addr3 == addr1

def test_root_size(monkeypatch):
    gclib.collect()
    myroots = gclib.GcRootCollection(16)
    monkeypatch.setattr(gclib, 'roots', myroots)
    p1 = gclib.new(ffi, 'Point*')
    p2 = gclib.new(ffi, 'Point*')
    p3 = gclib.new(ffi, 'Point*')
    gclib.collect()
    p4 = gclib.new(ffi, 'Point*')
    assert p4 not in (p1, p2, p3)
