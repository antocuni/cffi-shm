import py
import cffi
from shm import gclib
from shm.dict import lib, Dict
gclib.init('/run/shm/cffi-shm-testing')

ffi = cffi.FFI()

def check_dict(d):
    assert not lib.cfuhash_exists(d, "hello")
    lib.cfuhash_put(d, "hello", ffi.cast('void*', 42))
    assert lib.cfuhash_exists(d, "hello")
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
    

def test_getsetitem():
    d = Dict(ffi, 'const char*', 'long')
    py.test.raises(KeyError, "d['hello']")
    d['hello'] = 42
    assert d['hello'] == 42

def test_strvalue():
    d = Dict(ffi, 'const char*', 'const char*')
    d['hello'] = 'world'
    assert d['hello'] == 'world'
