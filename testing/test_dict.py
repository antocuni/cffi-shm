import py
import cffi
from shm import gclib
from shm.dict import lib
gclib.init('/run/shm/cffi-shm-testing')

ffi = cffi.FFI()

def test_libcfu():
    d = lib.cfuhash_new()
    assert not lib.cfuhash_exists(d, "hello")
    lib.cfuhash_put(d, "hello", ffi.cast('void*', 42))
    assert lib.cfuhash_exists(d, "hello")
    value = lib.cfuhash_get(d, "hello")
    assert int(ffi.cast("long", value)) == 42
