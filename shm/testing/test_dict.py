import py
import pytest
import cffi
from shm import gclib
from shm.dict import lib, DictType
from shm.pyffi import PyFFI
gclib.init('/cffi-shm-testing')

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
    # first, we check that it works with the system malloc
    d = lib.cfuhash_new()
    check_dict(ffi, d)
    lib.cfuhash_destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d < gc_base_mem

def test_libcfu_gc(ffi):
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

def test_keys(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    d['baz'] = 3
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']

def test_from_pointer(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT(root=True)
    d['hello'] = 1
    d['world'] = 2
    ptr = pyffi.ffi.cast('void*', d.ht)
    #
    d2 = DT.from_pointer(ptr)
    assert d2['hello'] == 1
    assert d2['world'] == 2


def test_key_struct_byval(pyffi):
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            char first_name[20];
            char last_name[20];
        } FullName;
    """)

    @pyffi.struct('FullName*')
    class FullName(object):
        pass

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


def test_key_struct_byptr(pyffi):
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            char first_name[20];
            char last_name[20];
        } FullName;
    """)

    @pyffi.struct('FullName*')
    class FullName(object):
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
