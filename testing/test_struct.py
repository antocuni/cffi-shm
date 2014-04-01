import py
import cffi
from shm import gclib
from shm.pyffi import PyFFI
gclib.init('/cffi-shm-testing')

ffi = cffi.FFI()

ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;
""")

def test_immutable_struct():
    pyffi = PyFFI(ffi)
    
    @pyffi.struct('Point*', immutable=True)
    class Point(object):
        def hypot(self):
            import math
            return math.sqrt(self.x**2 + self.y**2)
    #
    assert pyffi.pytypeof('Point*') is Point
    p = Point(x=3, y=4)
    assert p.x == 3
    assert p.y == 4
    assert p.hypot() == 5
    py.test.raises(AttributeError, "p.x = 0")
    py.test.raises(AttributeError, "p.y = 0")
    #
    p._ptr.x = 0
    assert p.x == 0

def test_mutable_struct():
    pyffi = PyFFI(ffi)    
    
    @pyffi.struct('Point*')
    class Point(object):
        def hypot(self):
            import math
            return math.sqrt(self.x**2 + self.y**2)
    #
    p = Point(x=3, y=4)
    assert p.x == 3
    assert p.y == 4
    assert p.hypot() == 5
    assert p._ptr.x == 3
    p.x = 0
    p.y = 0
    assert p._ptr.x == 0
