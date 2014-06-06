import py
import cffi
from shm.sharedmem import sharedmem
from shm.pyffi import PyFFI
from shm.converter import AbstractConverter
sharedmem.init('/cffi-shm-testing')

ffi = cffi.FFI()

ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;

    typedef struct {
        Point* a;
        Point* b;
    } Rectangle;
""")

def test_immutable_struct():
    pyffi = PyFFI(ffi)
    Point = pyffi.struct('Point')
    assert isinstance(Point, type)
    assert pyffi.pytypeof('Point') is Point
    assert pyffi.pytypeof('Point*') is Point
    p = Point(x=3, y=4)
    assert p.x == 3
    assert p.y == 4
    py.test.raises(AttributeError, "p.x = 0")
    py.test.raises(AttributeError, "p.y = 0")
    py.test.raises(AttributeError, "p.I_dont_exist = 0")
    #
    p._ptr.x = 0
    assert p.x == 0

def test_mutable_struct():
    pyffi = PyFFI(ffi)
    Point = pyffi.struct('Point', immutable=False)
    p = Point(x=3, y=4)
    assert p.x == 3
    assert p.y == 4
    py.test.raises(AttributeError, "p.I_dont_exist = 0")
    assert p._ptr.x == 3
    p.x = 0
    p.y = 0
    assert p._ptr.x == 0

def test_inheritance():
    pyffi = PyFFI(ffi)
    class Point(pyffi.struct('Point')):
        def hypot(self):
            import math
            return math.sqrt(self.x**2 + self.y**2)
    #
    assert pyffi.pytypeof('Point*') is Point
    p = Point(x=3, y=4)
    assert p.x == 3
    assert p.y == 4
    assert p.hypot() == 5

def test_override_init():
    pyffi = PyFFI(ffi)
    class Point(pyffi.struct('Point')):
        def __init__(self):
            self._init(x=1, y=2)
    #
    p = Point()
    assert p.x == 1
    assert p.y == 2


def test_nested_struct():
    pyffi = PyFFI(ffi)

    Point = pyffi.struct('Point', immutable=False)
    Rectangle = pyffi.struct('Rectangle', immutable=False)

    p1 = Point(1, 2)
    p2 = Point(3, 4)
    rect = Rectangle(p1, p2)
    assert isinstance(rect.a, Point)
    assert rect.a is not p1 # not the same object
    assert rect.a.x == 1
    p1.x = 100
    assert rect.a.x == 100  # but pointing to the same memory

def test_equality_hash():
    pyffi = PyFFI(ffi)
    Point = pyffi.struct('Point')
    p1 = Point(1, 2)
    p2 = Point(1, 2)
    assert hash(p1) == hash(p2)
    assert p1 == p2
    assert p1 != None # check that the exception is not propagated outside __eq__


def test_string():
    from shm import gclib
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct {
            const char* name;
        } Person;
    """)
    pyffi = PyFFI(ffi)
    Person = pyffi.struct('Person')
    p = Person('Foobar')
    assert p.name == 'Foobar'
    assert gclib.isptr(p._ptr.name)
    assert ffi.string(p._ptr.name) == 'Foobar'

def test_array_of_chars():
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct {
            char name[20];
        } Person;
    """)
    pyffi = PyFFI(ffi)
    Person = pyffi.struct('Person')
    p = Person('Foobar')
    assert p.name == 'Foobar'
    assert ffi.string(p._ptr.name) == 'Foobar'


def test_list_field():
    from shm.list import FixedSizeList
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct LongList LongList;
        typedef struct {
            LongList* mylist;
        } MyStruct;
    """)
    pyffi = PyFFI(ffi)

    LongList = pyffi.list('long', cname='LongList')
    MyStruct = pyffi.struct('MyStruct')
    #
    mylist = LongList(range(5))
    obj = MyStruct(mylist)
    assert isinstance(obj.mylist, FixedSizeList)
    assert list(obj.mylist) == range(5)


def test_dict_field():
    from shm.dict import DictType, DictInstance
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct PersonDB PersonDB;
        typedef struct {
            PersonDB* db;
        } MyStruct;
    """)
    pyffi = PyFFI(ffi)

    PersonDB = pyffi.dict('const char*', 'long', cname='PersonDB')
    MyStruct = pyffi.struct('MyStruct')
    #
    db = PersonDB()
    db['foo'] = 32
    db['bar'] = 42
    obj = MyStruct(db)
    assert isinstance(obj.db, DictInstance)
    assert obj.db['foo'] == 32
    assert obj.db['bar'] == 42

def test_custom_converter():
    class MyConverter(AbstractConverter):
        def to_python_impl(self, cdata):
            return float(cdata) * 2

        def from_python(self, obj, ensure_shm=True):
            return obj+1

    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct {
            double x;
        } MyStruct;
    """)
    pyffi = PyFFI(ffi)
    converters = {'x': MyConverter}
    MyStruct = pyffi.struct('MyStruct', converters=converters)
    obj = MyStruct(20)
    assert obj._ptr.x == 21
    assert obj.x == 42

