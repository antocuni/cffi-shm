import pytest
import cffi
from shm.sharedmem import sharedmem
from shm.libcfu import cfuffi, cfuhash, FieldSpec
sharedmem.init('/cffi-shm-testing')

@pytest.fixture
def ffi():
    return cffi.FFI()


def check_dict(ffi, d):
    keysize = ffi.cast('size_t', -1)
    assert not cfuhash.exists_data(d, "hello", keysize)
    cfuhash.put_data(d, "hello", keysize,
                         ffi.cast('void*', 42), 0, ffi.NULL)
    assert cfuhash.exists_data(d, "hello", keysize)
    value = cfuhash.get(d, "hello")
    assert int(ffi.cast("long", value)) == 42

def test_libcfu(ffi):
    from shm import gclib
    # first, we check that it works with the system malloc
    d = cfuhash.new()
    check_dict(ffi, d)
    cfuhash.destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d < gc_base_mem

def test_libcfu_gc(ffi):
    from shm import gclib
    # then, we check that it works with the the GC malloc
    d = cfuhash.new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                       gclib.lib.get_GC_free())
    check_dict(ffi, d)
    cfuhash.destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d >= gc_base_mem

def generic_cmp(fieldspec, p1, p2):
    ptrspec = fieldspec.getptr()
    res = cfuhash.generic_cmp(ptrspec, p1, p2)
    h1 = cfuhash.generic_hash(ptrspec, p1)
    h2 = cfuhash.generic_hash(ptrspec, p2)
    if res == 0:
        assert h1 == h2
    else:
        assert h1 != h2
    return res

def test_libcfu_generic_cmp_primitive(ffi):
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
            long z;
        } Point;
    """)
    def Point(x, y, z):
        p = ffi.new('Point*')
        p.x = x
        p.y = y
        p.z = z
        return p
    #
    point_spec = FieldSpec(ffi, 'Point')
    point_spec.add('x', cfuhash.primitive, ffi.sizeof('long'))
    point_spec.add('y', cfuhash.primitive, ffi.sizeof('long'))
    point_spec.add('z', cfuhash.primitive, ffi.sizeof('long'))
    
    p1 = Point(1, 2, 3)
    p2 = Point(1, 2, 3)
    p3 = Point(1, 2, 300)
    assert generic_cmp(point_spec, p1, p2) == 0
    assert generic_cmp(point_spec, p1, p3) < 0
    assert generic_cmp(point_spec, p3, p1) > 0
    #
    # now we "cut" the fieldspec to ignore z, so that p1 and p3 are equal
    point_spec.ptr[2].kind = cfuhash.fieldspec_stop
    assert generic_cmp(point_spec, p1, p2) == 0
    assert generic_cmp(point_spec, p1, p3) == 0


def test_libcfu_generic_cmp_string(ffi):
    ffi.cdef("""
        typedef struct {
            const char* name;
            const char* surname;
            const char* empty;
        } Person;
    """)
    keepalive = []
    def Person(name, surname):
        name = ffi.new('char[]', name)
        surname = ffi.new('char[]', surname)
        keepalive.append(name)
        keepalive.append(surname)
        #
        p = ffi.new('Person*')
        p.name = name
        p.surname = surname
        p.empty = ffi.NULL
        return p
    #
    person_spec = FieldSpec(ffi, 'Person')
    person_spec.add('name', cfuhash.string, 0)
    person_spec.add('surname', cfuhash.string, 0)
    person_spec.add('empty', cfuhash.string, 0)

    p1 = Person('Hello', 'World')
    p2 = Person('Hello', 'World')
    p3 = Person('Hello', 'ZZZ')
    assert generic_cmp(person_spec, p1, p2) == 0
    assert generic_cmp(person_spec, p1, p3) < 0
    assert generic_cmp(person_spec, p3, p1) > 0
    #
    # now we "cut" the fieldspec to ignore surname, so that p1 and p3 are equal
    person_spec.ptr[1].kind = cfuhash.fieldspec_stop
    assert generic_cmp(person_spec, p1, p2) == 0
    assert generic_cmp(person_spec, p1, p3) == 0

def test_libcfu_generic_cmp_pointer_x(ffi):
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;

        typedef struct  {
            Point *a;
            Point *b;
            Point *c;
        } Rectangle;
    """)
    keepalive = []
    def Rectangle(p1, p2):
        p1 = ffi.new('Point*', p1)
        p2 = ffi.new('Point*', p2)
        r = ffi.new('Rectangle*')
        r.a = p1
        r.b = p2
        r.c = ffi.NULL
        keepalive.append((r, p1, p2))
        return r
    #
    point_spec = FieldSpec(ffi, 'Point')
    point_spec.add('x', cfuhash.primitive, ffi.sizeof('long'))
    point_spec.add('y', cfuhash.primitive, ffi.sizeof('long'))
    #
    rect_spec = FieldSpec(ffi, 'Rectangle')
    rect_spec.add('a', cfuhash.pointer, ffi.sizeof('Point'), fieldspec=point_spec, length=1)
    rect_spec.add('b', cfuhash.pointer, ffi.sizeof('Point'), fieldspec=point_spec, length=1)
    rect_spec.add('c', cfuhash.pointer, ffi.sizeof('Point'), fieldspec=point_spec, length=1)
    #
    r1 = Rectangle((1, 2), (3, 4))
    r2 = Rectangle((1, 2), (3, 4))
    r3 = Rectangle((1, 2), (5, 6))
    #
    assert generic_cmp(rect_spec, r1, r2) == 0
    assert generic_cmp(rect_spec, r1, r3) != 0

def test_libcfu_generic_cmp_pointer_fixedlen(ffi):
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;
        typedef struct {
            Point* points;
        } PointList;
    """)
    #
    point_spec = FieldSpec(ffi, 'Point')
    point_spec.add('x', cfuhash.primitive, ffi.sizeof('long'))
    point_spec.add('y', cfuhash.primitive, ffi.sizeof('long'))
    #
    pointlist_spec = FieldSpec(ffi, 'PointList')
    pointlist_spec.add('points', cfuhash.pointer, size = ffi.sizeof('Point'),
                       fieldspec = point_spec, length = 2)
    #
    pl1 = ffi.new('PointList*')
    pl1.points = p1 = ffi.new('Point[]', 2)
    pl1.points[0] = (1, 2)
    pl1.points[1] = (3, 4)
    #
    pl2 = ffi.new('PointList*')
    pl2.points = p2 = ffi.new('Point[]', 2)
    pl2.points[0] = (1, 2)
    pl2.points[1] = (3, 4)
    
    assert generic_cmp(pointlist_spec, pl1, pl2) == 0
    #
    # now we make them different
    p2[1].y = 400
    assert generic_cmp(pointlist_spec, pl1, pl2) != 0
    #
    # now we change the spec to consider only the first item, so they are
    # "equal" again
    pointlist_spec.ptr[0].length = 1
    assert generic_cmp(pointlist_spec, pl1, pl2) == 0


def test_libcfu_generic_cmp_array(ffi):
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;
        typedef struct {
            long n;
            Point* points;
        } PointList;
    """)
    #
    point_spec = FieldSpec(ffi, 'Point')
    point_spec.add('x', cfuhash.primitive, ffi.sizeof('long'))
    point_spec.add('y', cfuhash.primitive, ffi.sizeof('long'))
    #
    pointlist_spec = FieldSpec(ffi, 'PointList')
    pointlist_spec.add('n', cfuhash.primitive, ffi.sizeof('long'))
    pointlist_spec.add('points', cfuhash.array, size = ffi.sizeof('Point'),
                       fieldspec = point_spec, length_offset = 0)
    #
    pl1 = ffi.new('PointList*')
    pl1.n = 2
    pl1.points = p1 = ffi.new('Point[]', 2)
    pl1.points[0] = (1, 2)
    pl1.points[1] = (3, 4)
    #
    pl2 = ffi.new('PointList*')
    pl2.n = 2
    pl2.points = p2 = ffi.new('Point[]', 2)
    pl2.points[0] = (1, 2)
    pl2.points[1] = (3, 4)
    
    assert generic_cmp(pointlist_spec, pl1, pl2) == 0
    #
    # now we make them different
    p2[1].y = 400
    assert generic_cmp(pointlist_spec, pl1, pl2) != 0
    #
    # now we tell it to consider only the first item, so they are equal again
    pl1.n = 1
    pl2.n = 1
    assert generic_cmp(pointlist_spec, pl1, pl2) == 0
    #
    # finally, we check that if we have different lenghts, they are considered different
    pl2.n = 2
    assert generic_cmp(pointlist_spec, pl1, pl2) != 0

