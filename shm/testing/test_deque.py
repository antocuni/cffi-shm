import py
import cffi
from shm.sharedmem import sharedmem
from shm.testing.test_dict import pyffi
sharedmem.init('/cffi-shm-testing')

def test_ctor(pyffi):
    DT = pyffi.deque('long')
    d = DT()
    d.append(42)
    assert d[0] == 42
    assert len(d) == 1

def test_popleft(pyffi):
    DT = pyffi.deque('long')
    d = DT([1, 2, 3, 4])
    assert list(d) == [1, 2, 3, 4]
    assert d.popleft() == 1
    assert len(d) == 3
    assert d[0] == 2
    assert d[1] == 3
    assert d[2] == 4
    assert d[-1] == 4
    assert d[-2] == 3
    assert d[-3] == 2
    py.test.raises(IndexError, "d[3]")
    py.test.raises(IndexError, "d[-4]")
