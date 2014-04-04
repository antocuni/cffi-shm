import py
import cffi
from shm import gclib
from shm.pyffi import PyFFI
from shm.list import ListType
gclib.init('/cffi-shm-testing')

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
    LT = ListType(pyffi, 'long')
    l = LT()
    l.append(42)
    assert len(l) == 1
    l.append(43)
    assert len(l) == 2
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43

def test_growing(pyffi):
    LT = ListType(pyffi, 'long')
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