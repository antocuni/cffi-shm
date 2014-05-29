import py
import cffi
from shm import gclib
from shm.pyffi import AbstractGenericType
from shm.util import cffi_is_string, cffi_is_struct_ptr, cffi_is_struct

ROOTDIR = py.path.local(__file__).dirpath('..')
GCDIR = ROOTDIR.join('GC')
old_cwd = ROOTDIR.chdir()

dictffi = cffi.FFI()
dictffi.cdef("""
    static const int CFUHASH_NOCOPY_KEYS;
    static const int CFUHASH_NO_LOCKING;

    typedef ... cfuhash_table_t;
    typedef unsigned int (*cfuhash_function_t)(const void *key, size_t length);
    typedef int (*cfuhash_cmp_t)(const void *key1, size_t length1,
                                 const void *key2, size_t length2);
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
    void * cfuhash_delete_data(cfuhash_table_t *ht, const void *key, size_t key_size);
    void **cfuhash_keys(cfuhash_table_t *ht, size_t *num_keys, int fast);

    int cfuhash_set_hash_function(cfuhash_table_t *ht, cfuhash_function_t hf);
    int cfuhash_set_cmp_function(cfuhash_table_t *ht, cfuhash_cmp_t cmpf);

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

class DictType(AbstractGenericType):
    def __init__(self, pyffi, keytype, valuetype, default_factory=None):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.nocopy = False # by default, keys are copied
        self.c_hash = None
        self.c_cmp = None
        self.keytype = keytype
        self.valuetype = valuetype
        self.default_factory = default_factory
        if cffi_is_string(self.ffi, keytype):
            self.keysize = self.ffi.cast('size_t', -1)
        elif cffi_is_struct_ptr(self.ffi, keytype):
            self.nocopy = True
            self.keysize = self.ffi.cast('size_t', 0)
        elif cffi_is_struct(self.ffi, keytype):
            self.nocopy = True
            self.keysize = self.ffi.sizeof(keytype)
            pytype = pyffi.pytypeof(keytype)
            self.c_hash = pytype.__c_hash__
            self.c_cmp = pytype.__c_cmp__
        else: # primitive types
            # by setting keysize to 0, we compare the void* pointers directly,
            # not their content. Note that 'long' and 'double' keys will be
            # casted to void*, and we surely don't want to dereference them :)            
            self.nocopy = True
            self.keysize = 0
        #
        self.keyconverter = pyffi.get_converter(keytype, allow_structs_byval=True)
        self.valueconverter = pyffi.get_converter(valuetype)

    def __repr__(self):
        return '<shm type dict [%s: %s]>' % (self.keytype, self.valuetype)

    def __call__(self, root=True):
        with gclib.disabled:
            ptr = lib.cfuhash_new_with_malloc_fn(gclib.lib.get_GC_malloc(),
                                                 gclib.lib.get_GC_free())
        if self.nocopy:
            lib.cfuhash_set_flag(ptr, lib.CFUHASH_NOCOPY_KEYS)
        if self.c_hash:
            c_hash = dictffi.cast('cfuhash_function_t', self.c_hash)
            c_cmp = dictffi.cast('cfuhash_cmp_t', self.c_cmp)
            lib.cfuhash_set_hash_function(ptr, c_hash)
            lib.cfuhash_set_cmp_function(ptr, c_cmp)
        #
        if root:
            ptr = gclib.roots.add(dictffi, ptr)
        # NOTE: it is very important that we call _from_ht and not
        # from_pointer, because the latter does a cast, which means that the
        # original cdata to which we attached the root is destroied, and thus
        # the root is freed.
        return self._from_ht(ptr)

    def from_pointer(self, ptr):
        ht = dictffi.cast('cfuhash_table_t*', ptr)
        return self._from_ht(ht)

    def _from_ht(self, ht):
        if self.default_factory is not None:
            return DefaultDictInstance(self, ht, self.default_factory)
        else:
            return DictInstance(self, ht)





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

    def as_cdata(self):
        return self.ht

    def _key(self, key):
        return self.dictype.keyconverter.from_python(key, ensure_shm=False, as_voidp=True)

    def __getitem__(self, ckey):
        t = self.dictype
        key = self._key(ckey)
        ret = lib.cfuhash_get_data(self.ht, key, t.keysize,
                                   self.retbuffer, dictffi.NULL)
        if ret == 0:
            return self.__missing__(ckey)
        value = self.retbuffer[0]
        value = t.ffi.cast(t.valuetype, value)
        return t.valueconverter.to_python(value)

    def __missing__(self, key):
        raise KeyError(key)

    def __setitem__(self, key, value):
        t = self.dictype
        key = self._key(key)
        value = t.valueconverter.from_python(value)
        value = t.ffi.cast('void*', value)
        lib.cfuhash_put_data(self.ht, key, t.keysize, value, 0, dictffi.NULL)

    def __contains__(self, key):
        t = self.dictype
        key = self._key(key)
        return bool(lib.cfuhash_exists_data(self.ht, key, t.keysize))

    def __delitem__(self, key):
        t = self.dictype
        key = self._key(key)
        ret = lib.cfuhash_delete_data(self.ht, key, t.keysize)
        if ret == t.ffi.NULL:
            raise KeyError(key)

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
                key = t.keyconverter.to_python(key, force_cast=True)
                keys.append(key)
            return keys
        finally:
            lib.free(keys_array)

class DefaultDictInstance(DictInstance):

    def __init__(self, dictype, ht, default_factory):
        DictInstance.__init__(self, dictype, ht)
        self.default_factory = default_factory

    def __missing__(self, key):
        value = self.default_factory()
        self[key] = value
        return value
