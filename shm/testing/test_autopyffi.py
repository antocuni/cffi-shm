import cffi
from shm.struct import BaseStruct
from shm.autopyffi import AutoPyFFI
from shm import gclib
gclib.init('/cffi-shm-testing')


def test_ImmutableStruct():
    ffi = cffi.FFI()
    pyffi = AutoPyFFI(ffi)
    class Point(pyffi.ImmutableStruct):
        """
        typedef struct {
            int x;
            int y;
        } Point;
        """
    assert BaseStruct in Point.__mro__
    assert pyffi.ImmutableStruct not in Point.__mro__
    assert Point.ctype is ffi.typeof('Point*')

def test_Struct():
    ffi = cffi.FFI()
    pyffi = AutoPyFFI(ffi)
    class Point(pyffi.Struct):
        """
        typedef struct {
            int x;
            int y;
        } Point;
        """
    assert BaseStruct in Point.__mro__
    assert pyffi.Struct not in Point.__mro__
    assert Point.ctype is ffi.typeof('Point*')
    #
    # check that it's actually mutable
    p = Point(1, 2)
    p.x = 4
    assert p.x == 4
