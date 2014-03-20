import py
import cffi
from shm import gclib
from shm.converter import get_converter

ROOTDIR = py.path.local(__file__).dirpath('..')
GCDIR = ROOTDIR.join('GC')
old_cwd = ROOTDIR.chdir()

dictffi = cffi.FFI()
dictffi.cdef("""
    typedef ... cfuhash_table_t;
    typedef void* (*cfuhash_malloc_fn_t)(size_t size);
    typedef void (*cfuhash_free_fn_t)(void *data);

    cfuhash_table_t * cfuhash_new(void);
    cfuhash_table_t * cfuhash_new_with_malloc_fn(cfuhash_malloc_fn_t malloc_fn,
                                                 cfuhash_free_fn_t free_fn);
    int cfuhash_destroy(cfuhash_table_t *ht);
    void * cfuhash_get(cfuhash_table_t *ht, const char *key);
    int cfuhash_exists(cfuhash_table_t *ht, const char *key);
    void * cfuhash_put(cfuhash_table_t *ht, const char *key, void *data);
""")

lib = dictffi.verify(
    """
    #include "cfuhash.h"
    """,
    sources = ['shm/libcfu/cfuhash.c'],
    include_dirs = ['shm/libcfu'],
    #extra_compile_args = ['-g', '-O0'],
)
old_cwd.chdir()

class Dict(object):

    def __init__(self, ffi, keytype, valuetype, root=False):
        self.ffi = ffi
        assert keytype in ('const char*', 'char*'), 'only string keys are supported for now'
        self.keytype = keytype
        self.valuetype = valuetype
        self.keyconverter = get_converter(ffi, keytype)
        self.valueconverter = get_converter(ffi, valuetype)
        self.d = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                                gclib.lib.get_GC_free())
        if root:
            gclib.roots.add(self.d)


    def __getitem__(self, key):
        key = self.keyconverter.from_python(self.ffi, key)
        value = lib.cfuhash_get(self.d, key)
        if value == dictffi.NULL:
            raise KeyError(key)
        value = self.ffi.cast(self.valuetype, value)
        return self.valueconverter.to_python(self.ffi, value)

    def __setitem__(self, key, value):
        key = self.keyconverter.from_python(self.ffi, key)
        value = self.valueconverter.from_python(self.ffi, value)
        value = self.ffi.cast('void*', value)
        lib.cfuhash_put(self.d, key, value)

    def __contains__(self, key):
        key = self.keyconverter.from_python(self.ffi, key)
        return bool(lib.cfuhash_exists(self.d, key))
