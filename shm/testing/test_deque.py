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
    assert d.popleft() == 2
    py.test.raises(IndexError, "d[3]")
    py.test.raises(IndexError, "d[-4]")

def test_popleft_empty(pyffi):
    DT = pyffi.deque('long')
    d = DT()
    py.test.raises(IndexError, "d.popleft()")
    d.append(42)
    assert d.popleft() == 42
    py.test.raises(IndexError, "d.popleft()")

def test_circular_buffer(pyffi):
    DT = pyffi.deque('long')
    d = DT([1, 2, 3, 4])
    assert d.lst.size == 4 # completely full
    assert d.popleft() == 1
    assert d.lst.offset == 1
    d.append(5)
    assert d.lst.size == 4
    assert d[0] == 2
    assert d[3] == 5
    assert list(d.typeditems[0:4]) == [5, 2, 3, 4]

def test_popleft_circular(pyffi):
    DT = pyffi.deque('long')
    d = DT([10, 20])
    assert d.lst.size == 2
    assert d.lst.offset == 0
    assert d.popleft() == 10
    assert d.lst.offset == 1
    assert d.popleft() == 20
    assert d.lst.offset == 0
    d.append(30)
    assert d.typeditems[0] == 30


def test_growing(pyffi):
    DT = pyffi.deque('long')
    #
    # start with a buffer of 4 items and offset==1
    d = DT([100])
    d._grow(4)
    assert d.popleft() == 100
    assert d.lst.offset == 1
    assert d.lst.size == 4
    assert d.lst.length == 0
    #
    # fill the circular buffer
    d.append(1)
    d.append(2)
    d.append(3)
    d.append(4)
    assert list(d.typeditems[0:4]) == [4, 1, 2, 3]
    #
    # now grow, and reshuffle the buffer
    d.append(5)
    assert list(d.typeditems[0:5]) == [1, 2, 3, 4, 5]
    assert d.lst.offset == 0
    assert len(d) == 5
    
def test___iter__(pyffi):
    DT = pyffi.deque('long')
    #
    # start with a buffer of 4 items and offset==1
    d = DT([1, 2, 3])
    assert list(d) == [1, 2, 3]
    d.append(4)
    assert list(d) == [1, 2, 3, 4]
    assert d.popleft() == 1
    assert list(d) == [2, 3, 4]
    d.append(5)
    d.append(6)
    assert list(d) == [2, 3, 4, 5, 6]

def test___setitem__(pyffi):
    DT = pyffi.deque('long')
    #
    # start with a buffer of 4 items and offset==1
    d = DT([1, 2, 3])
    assert d.popleft() == 1
    d[0] = 20
    d[1] = 30
    assert list(d) == [20, 30]

def test_slice(pyffi):
    DT = pyffi.deque('long')
    #
    # start with a buffer of 4 items and offset==1
    d = DT([1, 2, 3])
    assert d.popleft() == 1
    d.append(4)
    assert list(d[0:4]) == [2, 3, 4]

def test_null_on_delete(pyffi):
    DT = pyffi.deque('const char*')
    d = DT()
    d.append('hello')
    d.popleft()
    d.append('world')
    d.popleft()
    assert list(d.typeditems[0:2]) == [pyffi.ffi.NULL, pyffi.ffi.NULL]

def test_random(pyffi):
    from collections import deque
    import random
    import time
    seed = time.time
    print 'seed =', seed
    random.seed(seed)
    #
    DT = pyffi.deque('long')
    def tryit(size):
        ops = ['append']*(size*2) + ['popleft']*size
        random.shuffle(ops)
        shm_d = DT()
        py_d = deque()
        for i, op in enumerate(ops):
            if op == 'append':
                shm_d.append(i)
                py_d.append(i)
            elif op == 'popleft':
                if py_d:
                    x = shm_d.popleft()
                    y = py_d.popleft()
                    assert x == y
                else:
                    assert not shm_d
            else:
                assert False, 'unknown op: %s' % op
        assert list(shm_d) == list(py_d)

    for i in range(100):
        for size in [8, 20, 40]:
            tryit(size)
