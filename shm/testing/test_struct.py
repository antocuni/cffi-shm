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

    typedef struct {
        Point* a;
        Point* b;
    } Rectangle;
""")

def test_immutable_struct():
    pyffi = PyFFI(ffi)
    
    @pyffi.struct('Point*')
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
    
    @pyffi.struct('Point*', immutable=False)
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

def test_override_init():
    pyffi = PyFFI(ffi)

    @pyffi.struct('Point*')
    class Point(object):
        def __init__(self):
            self._init(x=1, y=2)
    #
    p = Point()
    assert p.x == 1
    assert p.y == 2


def test_nested_struct():
    pyffi = PyFFI(ffi)

    @pyffi.struct('Point*', immutable=False)
    class Point(object):
        pass

    @pyffi.struct('Rectangle*', immutable=False)
    class Rectangle(object):
        pass

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

    @pyffi.struct('Point*')
    class Point(object):
        pass

    p1 = Point(1, 2)
    p2 = Point(1, 2)
    assert hash(p1) == hash(p2)
    assert p1 == p2
    assert p1 != None # check that the exception is not propagated outside __eq__


def test_string():
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct {
            const char* name;
        } Person;
    """)
    pyffi = PyFFI(ffi)

    @pyffi.struct('Person*')
    class Person(object):
        pass

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

    @pyffi.struct('Person*')
    class Person(object):
        pass

    p = Person('Foobar')
    assert p.name == 'Foobar'
    assert ffi.string(p._ptr.name) == 'Foobar'


def test_list_field():
    from shm.list import ListType, FixedSizeListInstance
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct LongList LongList;
        typedef struct {
            LongList* mylist;
        } MyStruct;
    """)
    pyffi = PyFFI(ffi)

    LongList = ListType(pyffi, 'long')
    pyffi.register('LongList*', LongList)

    @pyffi.struct('MyStruct*')
    class MyStruct(object):
        pass

    mylist = LongList(range(5))
    obj = MyStruct(mylist)
    assert isinstance(obj.mylist, FixedSizeListInstance)
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

    PersonDB = DictType(pyffi, 'const char*', 'long')
    pyffi.register('PersonDB*', PersonDB)

    @pyffi.struct('MyStruct*')
    class MyStruct(object):
        pass

    db = PersonDB()
    db['foo'] = 32
    db['bar'] = 42
    obj = MyStruct(db)
    assert isinstance(obj.db, DictInstance)
    assert obj.db['foo'] == 32
    assert obj.db['bar'] == 42
