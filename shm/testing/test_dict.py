import py
import pytest
import cffi
from shm.sharedmem import sharedmem
from shm.dict import lib, DictType
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

    # first: we use struct by value as keys
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


def test_key_struct_byptr(pyffi):
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

    # second: we use struct by pointer, i.e. antocuni and antocuni2 are
    # different keys
    DT = DictType(pyffi, 'FullName*', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d.get(antocuni2) is None
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]


def test_key_hash(pyffi):
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

    # third: we use struct by value, but we rely on the custom cmp function
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
