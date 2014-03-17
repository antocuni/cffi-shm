from shm import gclib
from shm.list import List
gclib.init('/run/shm/cffi-shm-testing')

def test_newlist():
    l = List()
    assert l.lst.size == 2
    assert l.lst.length == 0
    assert len(l) == 0

def test_append():
    l = List('long')
    l.append(42)
    assert len(l) == 1
    l.append(43)
    assert len(l) == 2
    assert l.typeditems[0] == 42
    assert l.typeditems[1] == 43
