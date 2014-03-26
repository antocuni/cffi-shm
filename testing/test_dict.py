import py
import cffi
from shm import gclib
from shm.dict import lib, DictType
gclib.init('/run/shm/cffi-shm-testing')

ffi = cffi.FFI()
ffi.cdef("""
    typedef struct {
        char first_name[20];
        char last_name[20];
    } full_name_t;
""")

def check_dict(d):
    keysize = ffi.cast('size_t', -1)
    assert not lib.cfuhash_exists_data(d, "hello", keysize)
    lib.cfuhash_put_data(d, "hello", keysize,
                         ffi.cast('void*', 42), 0, ffi.NULL)
    assert lib.cfuhash_exists_data(d, "hello", keysize)
    value = lib.cfuhash_get(d, "hello")
    assert int(ffi.cast("long", value)) == 42

def test_libcfu():
    # first, we check that it works with the system malloc
    d = lib.cfuhash_new()
    check_dict(d)
    lib.cfuhash_destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d < gc_base_mem

def test_libcfu_gc():
    # then, we check that it works with the the GC malloc
    d = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                       gclib.lib.get_GC_free())
    check_dict(d)
    lib.cfuhash_destroy(d)
    #
    gc_base_mem = gclib.lib.GC_get_memory()
    assert d >= gc_base_mem

def test_DictType():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    assert repr(DT) == '<shm type dict [const char*: long]>'

def test_getsetitem():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    d = DT()
    py.test.raises(KeyError, "d['hello']")
    d['hello'] = 42
    assert d['hello'] == 42

def test_strvalue():
    DT = DictType(ffi, 'const char*', ffi, 'const char*')
    d = DT()
    d['hello'] = 'world'
    assert d['hello'] == 'world'

def test_contains():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    d = DT()
    assert 'hello' not in d
    d['hello'] = 42
    assert 'hello' in d

def test_get():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    d = DT()
    assert d.get('hello') is None
    assert d.get('hello', 123) == 123
    d['hello'] = 42
    assert d.get('hello') == 42

def test_keys():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    d['baz'] = 3
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']

def test_from_pointer():
    DT = DictType(ffi, 'const char*', ffi, 'long')
    d = DT(root=True)
    d['hello'] = 1
    d['world'] = 2
    ptr = ffi.cast('void*', d.ht)
    #
    d2 = DT.from_pointer(ptr)
    assert d2['hello'] == 1
    assert d2['world'] == 2

def full_name(first, last):
    n = gclib.new(ffi, 'full_name_t*')
    n.first_name = first
    n.last_name = last
    return n


def test_struct_keys():
    DT = DictType(ffi, 'full_name_t', ffi, 'long')
    d = DT()
    antocuni = full_name('Antonio', 'Cuni')
    antocuni2 = full_name('Antonio', 'Cuni')
    wrongname = full_name('Antonio', 'Foobar')
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d[antocuni2] == 1
    assert d[wrongname] == 2
