import py
import cffi
from shm.sharedmem import sharedmem
from shm.pyffi import PyFFI
from shm.list import ListType, FixedSizeList, ResizableList
sharedmem.init('/cffi-shm-testing')

@py.test.fixture
def pyffi():
    return PyFFI(cffi.FFI())

def test_newlist(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT()
    assert l.lst.size == 2
    assert l.lst.length == 0
    assert len(l) == 0

def test_append(pyffi):
    LT = ListType(pyffi, 'long', ResizableList)
    l = LT()
    l.append(42)
    assert len(l) == 1
    l.append(43)
    assert len(l) == 2
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43

def test_growing(pyffi):
    LT = ListType(pyffi, 'long', ResizableList)
    l = LT()
    l.append(42)
    l.append(43)
    l.append(44)
    assert len(l) == 3
    assert l.lst.size == 4
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43
    assert l.typeditems[2] == 44

def test_init(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT([])
    assert len(l) == 0
    assert l.lst.size == 2
    #
    l = LT(range(5))
    assert len(l) == 5
    assert l.lst.size == 5
    assert l.typeditems[0] == 0
    assert l.typeditems[1] == 1
    assert l.typeditems[2] == 2
    assert l.typeditems[3] == 3
    assert l.typeditems[4] == 4

def test_getitem(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT(range(5))
    assert l[0] == 0
    assert l[4] == 4
    assert l[-5] == 0
    assert l[-1] == 4
    py.test.raises(IndexError, "l[5]")
    py.test.raises(IndexError, "l[-6]")
    
def test_setitem(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT(range(5))
    l[0] = 42
    l[4] = 43
    assert l[0] == 42
    assert l[-1] == 43

def test_iter(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT(range(5))
    assert list(l) == range(5)

def test_from_pointer(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT(range(5))
    ptr = pyffi.ffi.cast('void*', l.lst)
    l2 = LT.from_pointer(ptr)
    assert list(l2) == range(5)
    l2[0] = 42
    assert l[0] == 42

def test_list_of_structs(pyffi):
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            int x;
            int y;
        } Point;
    """)
    Point = pyffi.struct('Point')
    LT = ListType(pyffi, 'Point*')
    p1 = Point(1, 2)
    p2 = Point(3, 4)
    lst = LT([p1, p2])
    assert lst[0] == p1
    assert lst[1] == p2

def test_fixed_size_list(pyffi):
    LT = ListType(pyffi, 'long')
    l = LT(range(5))
    assert l[0] == 0
    assert l[4] == 4
    py.test.raises(AttributeError, "l.append(5)")

def test_inheritance(pyffi):
    class MyList(FixedSizeList):
        def foo(self):
            return len(self)*2

    LT = ListType(pyffi, 'long', MyList)
    l = LT(range(5))
    assert len(l) == 5
    assert l.foo() == 10
