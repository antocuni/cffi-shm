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

    void * cfuhash_get(cfuhash_table_t *ht, const char *key); /* used only in tests */
    int cfuhash_get_data(cfuhash_table_t *ht, const void *key, size_t key_size,
                         void **data, size_t *data_size);
    int cfuhash_put_data(cfuhash_table_t *ht, const void *key, size_t key_size, void *data,
	                 size_t data_size, void **r);
    int cfuhash_exists_data(cfuhash_table_t *ht, const void *key, size_t key_size);
    void **cfuhash_keys(cfuhash_table_t *ht, size_t *num_keys, int fast);

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

class DictType(object):
    def __init__(self, keyffi, keytype, valueffi, valuetype):
        assert keytype in ('const char*', 'char*'), 'only string keys are supported for now'
        self.keyffi = keyffi
        self.keytype = keytype
        self.keysize = keyffi.cast('size_t', -1)
        self.valueffi = valueffi
        self.valuetype = valuetype
        self.keyconverter = get_converter(keyffi, keytype)
        self.valueconverter = get_converter(valueffi, valuetype)

    def __repr__(self):
        return '<shm type dict [%s: %s]>' % (self.keytype, self.valuetype)

    def __call__(self, root=False):
        ptr = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                             gclib.lib.get_GC_free())
        if root:
            gclib.roots.add(ptr)
        return DictInstance(self, ptr)

    def from_pointer(self, ptr):
        ptr = dictffi.cast('cfuhash_table_t*', ptr)
        return DictInstance(self, ptr)

class DictInstance(object):

    def __init__(self, dictype, ht):
        self.dictype = dictype
        self.ht = ht
        self.retbuffer = dictffi.new('void*[1]') # passed to cfuhash_get_data

    def __repr__(self):
        addr = int(dictffi.cast('long', self.ht))
        return '<shm dict [%s: %s] at 0x%x>' % (self.dictype.keytype,
                                                self.dictype.valuetype,
                                                addr)

    def __getitem__(self, key):
        t = self.dictype
        ret = lib.cfuhash_get_data(self.ht, key, t.keysize,
                                   self.retbuffer, dictffi.NULL)
        if ret == 0:
            raise KeyError(key)
        value = self.retbuffer[0]
        value = t.valueffi.cast(t.valuetype, value)
        return t.valueconverter.to_python(t.valueffi, value)

    def __setitem__(self, key, value):
        t = self.dictype
        value = t.valueconverter.from_python(t.valueffi, value)
        value = t.valueffi.cast('void*', value)
        lib.cfuhash_put_data(self.ht, key, t.keysize, value, 0, dictffi.NULL)

    def __contains__(self, key):
        t = self.dictype
        return bool(lib.cfuhash_exists_data(self.ht, key, t.keysize))

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        t = self.dictype
        sizeptr = dictffi.new('size_t[1]')
        keys_array = lib.cfuhash_keys(self.ht, sizeptr, True)
        if keys_array == dictffi.NULL:
            raise MemoryError
        try:
            size = sizeptr[0]
            keys = []
            for i in range(size):
                key = keys_array[i]
                key = t.keyconverter.to_python(t.keyffi, key)
                keys.append(key)
            return keys
        finally:
            lib.free(keys_array)
