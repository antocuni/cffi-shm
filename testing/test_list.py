from shm import gclib
from shm.list import List
gclib.init('/run/shm/cffi-shm-testing')

def test_newlist():
    l = List()
    assert l.lst.size == 2
    assert l.lst.length == 0
    assert len(l) == 0
