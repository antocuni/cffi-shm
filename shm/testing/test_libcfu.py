import pytest
import cffi
from shm.sharedmem import sharedmem
from shm.libcfu import cfuffi, lib
sharedmem.init('/cffi-shm-testing')

@pytest.fixture
def ffi():
    return cffi.FFI()


def check_dict(ffi, d):
    keysize = ffi.cast('size_t', -1)
    assert not lib.cfuhash_exists_data(d, "hello", keysize)
    lib.cfuhash_put_data(d, "hello", keysize,
                         ffi.cast('void*', 42), 0, ffi.NULL)
    assert lib.cfuhash_exists_data(d, "hello", keysize)
    value = lib.cfuhash_get(d, "hello")
    assert int(ffi.cast("long", value)) == 42

def test_libcfu(ffi):
    from shm import gclib
    # first, we check that it works with the system malloc
    d = lib.cfuhash_new()
    check_dict(ffi, d)
    lib.cfuhash_destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d < gc_base_mem

def test_libcfu_gc(ffi):
    from shm import gclib
    # then, we check that it works with the the GC malloc
    d = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                       gclib.lib.get_GC_free())
    check_dict(ffi, d)
    lib.cfuhash_destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d >= gc_base_mem

def make_fieldspec(ffi, t, spec):
    n = len(spec)+1
    fields = dict(ffi.typeof(t).fields)
    fieldspec = cfuffi.new('cfuhash_fieldspec_t[]', n)
    for i, (fieldname, kind) in enumerate(spec):
        fieldspec[i].kind = kind
        fieldspec[i].offset = ffi.offsetof(t, fieldname)
        if kind == lib.cfuhash_pointer:
            fieldspec[i].length = 1
        else:
            fieldspec[i].size = ffi.sizeof(fields[fieldname].type)
    fieldspec[i+1].kind = lib.cfuhash_fieldspec_stop
    return fieldspec

def generic_cmp(fieldspec, p1, p2):
    res = lib.cfuhash_generic_cmp(fieldspec, p1, p2)
    h1 = lib.cfuhash_generic_hash(fieldspec, p1)
    h2 = lib.cfuhash_generic_hash(fieldspec, p2)
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
    point_spec = make_fieldspec(ffi, 'Point', [('x', lib.cfuhash_primitive),
                                               ('y', lib.cfuhash_primitive),
                                               ('z', lib.cfuhash_primitive)])
    p1 = Point(1, 2, 3)
    p2 = Point(1, 2, 3)
    p3 = Point(1, 2, 300)
    assert generic_cmp(point_spec, p1, p2) == 0
    assert generic_cmp(point_spec, p1, p3) < 0
    assert generic_cmp(point_spec, p3, p1) > 0
    #
    # now we "cut" the fieldspec to ignore z, so that p1 and p3 are equal
    point_spec[2].kind = lib.cfuhash_fieldspec_stop
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
    person_spec = make_fieldspec(ffi, 'Person', [('name', lib.cfuhash_string),
                                                 ('surname', lib.cfuhash_string),
                                                 ('empty', lib.cfuhash_string)])
    p1 = Person('Hello', 'World')
    p2 = Person('Hello', 'World')
    p3 = Person('Hello', 'ZZZ')
    assert generic_cmp(person_spec, p1, p2) == 0
    assert generic_cmp(person_spec, p1, p3) < 0
    assert generic_cmp(person_spec, p3, p1) > 0
    #
    # now we "cut" the fieldspec to ignore surname, so that p1 and p3 are equal
    person_spec[1].kind = lib.cfuhash_fieldspec_stop
    assert generic_cmp(person_spec, p1, p2) == 0
    assert generic_cmp(person_spec, p1, p3) == 0

def test_libcfu_generic_cmp_pointer(ffi):
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
    def Point(x, y):
        p = ffi.new('Point*')
        p.x = x
        p.y = y
        keepalive.append(p)
        return p
    def Rectangle(a, b):
        r = ffi.new('Rectangle*')
        r.a = a
        r.b = b
        r.c = ffi.NULL
        keepalive.append(r)
        return r
    #
    point_spec = make_fieldspec(ffi, 'Point', [('x', lib.cfuhash_primitive),
                                               ('y', lib.cfuhash_primitive)])
    rect_spec = make_fieldspec(ffi, 'Rectangle', [('a', lib.cfuhash_primitive),
                                                  ('b', lib.cfuhash_primitive),
                                                  ('c', lib.cfuhash_primitive)])
    p1 = Point(1, 2)
    p2 = Point(1, 2)
    p3 = Point(3, 4)
    #
    r1 = Rectangle(p1, p1)
    r2 = Rectangle(p2, p2)
    r3 = Rectangle(p3, p3)
    #
    # Rectangle.{a,b} are compared as primitive fields, so r1 and r2 are
    # different
    assert generic_cmp(rect_spec, r1, r2) != 0
    assert generic_cmp(rect_spec, r1, r3) != 0
    assert generic_cmp(rect_spec, r2, r3) != 0
    #
    # fix rect_spec to compare a and b as pointers
    for i in range(3):
        rect_spec[i].kind = lib.cfuhash_pointer
        rect_spec[i].fieldspec = point_spec
        rect_spec[i].length = 1
    assert generic_cmp(rect_spec, r1, r2) == 0 # now they are equal
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
    point_spec = make_fieldspec(ffi, 'Point', [('x', lib.cfuhash_primitive),
                                               ('y', lib.cfuhash_primitive)])
    pointlist_spec = make_fieldspec(ffi, 'PointList',
                                    [('points', lib.cfuhash_pointer)])
    #
    pointlist_spec[0].fieldspec = point_spec
    pointlist_spec[0].size = ffi.sizeof('Point')
    pointlist_spec[0].length = 2  # consider two points
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
    pointlist_spec[0].length = 1
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
    point_spec = make_fieldspec(ffi, 'Point', [('x', lib.cfuhash_primitive),
                                               ('y', lib.cfuhash_primitive)])
    pointlist_spec = make_fieldspec(ffi, 'PointList',
                                    [('n', lib.cfuhash_primitive),
                                     ('points', lib.cfuhash_array)])
    #
    pointlist_spec[1].fieldspec = point_spec
    pointlist_spec[1].size = ffi.sizeof('Point')
    pointlist_spec[1].length_offset = 0
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

