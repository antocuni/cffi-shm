import py
import pytest
import cffi
from shm.sharedmem import sharedmem
from shm.dict import dictffi, lib, DictType
from shm.pyffi import PyFFI
sharedmem.init('/cffi-shm-testing')

@pytest.fixture
def ffi():
    return cffi.FFI()

@pytest.fixture
def pyffi(ffi):
    return PyFFI(ffi)

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
    fieldspec = dictffi.new('cfuhash_fieldspec_t[]', n)
    for i, (fieldname, kind) in enumerate(spec):
        fieldspec[i].kind = kind
        fieldspec[i].offset = ffi.offsetof(t, fieldname)
        fieldspec[i].size = ffi.sizeof(fields[fieldname].type)
    fieldspec[i+1].kind = lib.cfuhash_fieldspec_stop
    return fieldspec
    

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
    assert lib.cfuhash_generic_cmp(point_spec, p1, p2) == 0
    assert lib.cfuhash_generic_cmp(point_spec, p1, p3) < 0
    assert lib.cfuhash_generic_cmp(point_spec, p3, p1) > 0
    #
    h1 = lib.cfuhash_generic_hash(point_spec, p1)
    h2 = lib.cfuhash_generic_hash(point_spec, p2)
    h3 = lib.cfuhash_generic_hash(point_spec, p3)
    assert h1 == h2
    assert h1 != h3
    #
    #
    # now we "cut" the fieldspec to ignore z, so that p1 and p3 are equal
    point_spec[2].kind = lib.cfuhash_fieldspec_stop
    assert lib.cfuhash_generic_cmp(point_spec, p1, p3) == 0
    #
    h1 = lib.cfuhash_generic_hash(point_spec, p1)
    h2 = lib.cfuhash_generic_hash(point_spec, p2)
    h3 = lib.cfuhash_generic_hash(point_spec, p3)
    assert h1 == h2 == h3


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
    assert lib.cfuhash_generic_cmp(person_spec, p1, p2) == 0
    assert lib.cfuhash_generic_cmp(person_spec, p1, p3) < 0
    assert lib.cfuhash_generic_cmp(person_spec, p3, p1) > 0
    #
    h1 = lib.cfuhash_generic_hash(person_spec, p1)
    h2 = lib.cfuhash_generic_hash(person_spec, p2)
    h3 = lib.cfuhash_generic_hash(person_spec, p3)
    assert h1 == h2
    assert h1 != h3
    #
    #
    # now we "cut" the fieldspec to ignore surname, so that p1 and p3 are equal
    person_spec[1].kind = lib.cfuhash_fieldspec_stop
    assert lib.cfuhash_generic_cmp(person_spec, p1, p3) == 0
    #
    h1 = lib.cfuhash_generic_hash(person_spec, p1)
    h2 = lib.cfuhash_generic_hash(person_spec, p2)
    h3 = lib.cfuhash_generic_hash(person_spec, p3)
    assert h1 == h2 == h3

def test_libcfu_generic_cmp_pointer(ffi):
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;

        typedef struct  {
            Point *a;
            Point *b;
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
        keepalive.append(r)
        return r
    #
    point_spec = make_fieldspec(ffi, 'Point', [('x', lib.cfuhash_primitive),
                                               ('y', lib.cfuhash_primitive)])
    rect_spec = make_fieldspec(ffi, 'Rectangle', [('a', lib.cfuhash_primitive),
                                                  ('b', lib.cfuhash_primitive)])
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
    assert lib.cfuhash_generic_cmp(rect_spec, r1, r2) != 0
    assert lib.cfuhash_generic_cmp(rect_spec, r1, r3) != 0
    #
    h1 = lib.cfuhash_generic_hash(rect_spec, r1)
    h2 = lib.cfuhash_generic_hash(rect_spec, r2)
    h3 = lib.cfuhash_generic_hash(rect_spec, r3)
    assert h1 != h2 != h3
    #
    #
    # fix rect_spec to compare a and b as pointers
    rect_spec[0].kind = lib.cfuhash_pointer
    rect_spec[0].fieldspec = point_spec
    rect_spec[1].kind = lib.cfuhash_pointer
    rect_spec[1].fieldspec = point_spec
    assert lib.cfuhash_generic_cmp(rect_spec, r1, r2) == 0 # now they are equal
    assert lib.cfuhash_generic_cmp(rect_spec, r1, r3) != 0
    #
    h1 = lib.cfuhash_generic_hash(rect_spec, r1)
    h2 = lib.cfuhash_generic_hash(rect_spec, r2)
    h3 = lib.cfuhash_generic_hash(rect_spec, r3)
    assert h1 == h2
    assert h1 != h3



def test_DictType(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    assert repr(DT) == '<shm type dict [const char*: long]>'

def test_getsetitem(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    py.test.raises(KeyError, "d['hello']")
    d['hello'] = 42
    assert d['hello'] == 42

def test_strvalue(pyffi):
    DT = DictType(pyffi, 'const char*', 'const char*')
    d = DT()
    d['hello'] = 'world'
    assert d['hello'] == 'world'

def test_contains(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    assert 'hello' not in d
    d['hello'] = 42
    assert 'hello' in d

def test_get(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    assert d.get('hello') is None
    assert d.get('hello', 123) == 123
    d['hello'] = 42
    assert d.get('hello') == 42

def test___delitem__(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['hello'] = 42
    assert 'hello' in d
    del d['hello']
    assert 'hello' not in d
    py.test.raises(KeyError, "del d['foo']")

def test_keys_values_items(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    d['baz'] = 3
    #
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']
    #
    values = d.values()
    assert sorted(values) == [1, 2, 3]
    #
    items = d.items()
    assert sorted(items) == [('bar', 2), ('baz', 3), ('foo', 1)]

def test_update(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d.update({'bar': 1, 'baz': 2})
    d.update([('foo', 3)])
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']

def test_ctor(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT({'bar': 1, 'baz': 2, 'foo': 3})
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']


def test_from_pointer(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['hello'] = 1
    d['world'] = 2
    ptr = pyffi.ffi.cast('void*', d.ht)
    #
    d2 = DT.from_pointer(ptr)
    assert d2['hello'] == 1
    assert d2['world'] == 2

def test_long_key(pyffi):
    DT = DictType(pyffi, 'long', 'long')
    d = DT()
    d[10] = 20
    d[20] = 40
    assert d[10] == 20
    assert d[20] == 40

def test_key_struct_byval(pyffi):
    # first: we use struct by value as keys, easy case
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            char first_name[20];
            char last_name[20];
        } FullName;
    """)

    class FullName(pyffi.struct('FullName')):
        # this is needed for 'sorted' below
        def __cmp__(self, other):
            return cmp(self._key(), other._key())

    antocuni = FullName('Antonio', 'Cuni')
    antocuni2 = FullName('Antonio', 'Cuni')
    wrongname = FullName('Antonio', 'Foobar')

    DT = DictType(pyffi, 'FullName', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d[antocuni2] == 1
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]


def test_key_struct_with_pointers(pyffi):
    # second: we use struct by value as keys: the keys are compared shallowly,
    # so if they contains two different pointers to the same string, they are
    # considered unequal
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            const char* first_name;
            const char* last_name;
        } FullName;
    """)

    class FullName(pyffi.struct('FullName')):
        # this is needed for 'sorted' below
        def __cmp__(self, other):
            return cmp(self._key(), other._key())

    antocuni = FullName('Antonio', 'Cuni')
    antocuni2 = FullName('Antonio', 'Cuni')
    wrongname = FullName('Antonio', 'Foobar')

    DT = DictType(pyffi, 'FullName', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d.get(antocuni2) is None
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]
    #
    # ------------------------------------
    #
    # third: keys are pointers to a struct, and comparison is done using the
    # "fieldspec", i.e. it's a deep comparison
    #
    DT = DictType(pyffi, 'FullName*', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d[antocuni2] == 1
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]


def test_defaultdict(pyffi):
    DT = pyffi.defaultdict('const char*', 'long', lambda: 42)
    d = DT()
    assert d['hello'] == 42
    assert 'hello' in d

def test_defaultdict_struct_keys(pyffi):
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;
    """)

    Point = pyffi.struct('Point')
    DT = pyffi.defaultdict('Point', 'long', lambda: 42)
    d = DT()
    p = Point(1, 2)
    assert d[p] == 42
