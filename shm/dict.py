import py
import cffi
from shm import gclib
from shm.converter import get_converter

ROOTDIR = py.path.local(__file__).dirpath('..')
GCDIR = ROOTDIR.join('GC')
old_cwd = ROOTDIR.chdir()

dictffi = cffi.FFI()
dictffi.cdef("""
    static const int CFUHASH_NOCOPY_KEYS;
    static const int CFUHASH_NO_LOCKING;

    typedef ... cfuhash_table_t;
    typedef void* (*cfuhash_malloc_fn_t)(size_t size);
    typedef void (*cfuhash_free_fn_t)(void *data);

    cfuhash_table_t * cfuhash_new(void);
    cfuhash_table_t * cfuhash_new_with_malloc_fn(cfuhash_malloc_fn_t malloc_fn,
                                                 cfuhash_free_fn_t free_fn);
    int cfuhash_destroy(cfuhash_table_t *ht);
    int cfuhash_exists(cfuhash_table_t *ht, const char *key);
    void **cfuhash_keys(cfuhash_table_t *ht, size_t *num_keys, int fast);

    void * cfuhash_get(cfuhash_table_t *ht, const char *key); /* used only in tests */
    int cfuhash_get_data(cfuhash_table_t *ht, const void *key, size_t key_size,
                         void **data, size_t *data_size);
    int cfuhash_put_data(cfuhash_table_t *ht, const void *key, size_t key_size, void *data,
	                 size_t data_size, void **r);

    unsigned int cfuhash_get_flags(cfuhash_table_t *ht);
    unsigned int cfuhash_set_flag(cfuhash_table_t *ht, unsigned int new_flag);
    unsigned int cfuhash_clear_flag(cfuhash_table_t *ht, unsigned int new_flag);

    void free(void* ptr); /* stdlib's free */
""")

lib = dictffi.verify(
    """
    #include <stdlib.h>
    #include "cfuhash.h"
    """,
    sources = ['shm/libcfu/cfuhash.c'],
    include_dirs = ['shm/libcfu'],
    #extra_compile_args = ['-g', '-O1'],
)
old_cwd.chdir()

class Dict(object):

    def __init__(self, ffi, keytype, valuetype, root=False):
        d = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                           gclib.lib.get_GC_free())
        if root:
            gclib.roots.add(d)
        self._init(ffi, keytype, valuetype, d)

    @classmethod
    def from_pointer(cls, ffi, keytype, valuetype, ptr):
        self = cls.__new__(cls)
        d = dictffi.cast('cfuhash_table_t*', ptr)
        self._init(ffi, keytype, valuetype, d)
        return self

    def _init(self, ffi, keytype, valuetype, d):
        self.ffi = ffi
        assert keytype in ('const char*', 'char*'), 'only string keys are supported for now'
        self.keytype = keytype
        self.keysize = dictffi.cast('size_t', -1)
        self.valuetype = valuetype
        self.keyconverter = get_converter(ffi, keytype)
        self.valueconverter = get_converter(ffi, valuetype)
        self.retvalue = self.ffi.new('void*[1]') # passed to cfuhash_get_data
        self.d = d

    def _key(self, key):
        # there is no need to explicitly allocate a GC string, because the hastable
        # already does a copy internally, using the provided GC_malloc
        #key = self.keyconverter.from_python(self.ffi, key)
        return key

    def __getitem__(self, key):
        key = self._key(key)
        ret = lib.cfuhash_get_data(self.d, key, self.keysize, self.retvalue, self.ffi.NULL)
        if ret == 0:
            raise KeyError(key)
        value = self.retvalue[0]
        value = self.ffi.cast(self.valuetype, value)
        return self.valueconverter.to_python(self.ffi, value)

    def __setitem__(self, key, value):
        key = self._key(key)
        value = self.valueconverter.from_python(self.ffi, value)
        value = self.ffi.cast('void*', value)
        lib.cfuhash_put_data(self.d, key, self.keysize, value, 0, self.ffi.NULL)

    def __contains__(self, key):
        key = self._key(key)
        return bool(lib.cfuhash_exists(self.d, key))

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        sizeptr = dictffi.new('size_t[1]')
        keys_array = lib.cfuhash_keys(self.d, sizeptr, True)
        if keys_array == dictffi.NULL:
            raise MemoryError
        try:
            size = sizeptr[0]
            keys = []
            for i in range(size):
                key = keys_array[i]
                key = self.keyconverter.to_python(self.ffi, key)
                keys.append(key)
            return keys
        finally:
            lib.free(keys_array)
