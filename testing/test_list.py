import py
import cffi
from shm import gclib
from shm.list import List
gclib.init('/run/shm/cffi-shm-testing')

ffi = cffi.FFI()

def test_newlist():
    l = List(ffi, 'long')
    assert l.lst.size == 2
    assert l.lst.length == 0
    assert len(l) == 0

def test_append():
    l = List(ffi, 'long')
    l.append(42)
    assert len(l) == 1
    l.append(43)
    assert len(l) == 2
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43

def test_growing():
    l = List(ffi, 'long')
    l.append(42)
    l.append(43)
    l.append(44)
    assert len(l) == 3
    assert l.lst.size == 4
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43
    assert l.typeditems[2] == 44

def test_init():
    l = List(ffi, 'long', [])
    assert len(l) == 0
    assert l.lst.size == 2
    #
    l = List(ffi, 'long', range(5))
    assert len(l) == 5
    assert l.lst.size == 5
    assert l.typeditems[0] == 0
    assert l.typeditems[1] == 1
    assert l.typeditems[2] == 2
    assert l.typeditems[3] == 3
    assert l.typeditems[4] == 4

def test_getitem():
    l = List(ffi, 'long', range(5))
    assert l[0] == 0
    assert l[4] == 4
    assert l[-5] == 0
    assert l[-1] == 4
    py.test.raises(IndexError, "l[5]")
    py.test.raises(IndexError, "l[-6]")
    
def test_setitem():
    l = List(ffi, 'long', range(5))
    l[0] = 42
    l[4] = 43
    assert l[0] == 42
    assert l[-1] == 43
    
