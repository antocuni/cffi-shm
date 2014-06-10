import py
import cffi

ROOTDIR = py.path.local(__file__).dirpath('..')
old_cwd = ROOTDIR.chdir()

cfuffi = cffi.FFI()
cfuffi.cdef("""
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

    typedef enum { 
        cfuhash_fieldspec_stop=0,
        cfuhash_primitive,
        cfuhash_pointer,
        cfuhash_array,
        cfuhash_string
    } cfuhash_fieldkind_t;

    typedef struct cfuhash_fieldspec {
        const char* name;
        cfuhash_fieldkind_t kind;
        size_t offset;
        struct cfuhash_fieldspec *fieldspec;
        size_t size;   /* cfuhash_primitive:       size in bytes of the field
                        * cfuhash_{pointer,array}: size in bytes of each item in the array
                        */
        union {
            size_t length;        /* cfuhash_pointer: number of items in the array */
            size_t length_offset; /* cfuhash_array: offset where to find the length field */
        };
    } cfuhash_fieldspec_t;

    int cfuhash_set_key_fieldspec(cfuhash_table_t *ht, cfuhash_fieldspec_t fs[]);
    int cfuhash_generic_cmp(cfuhash_fieldspec_t fields[], void* key1, void* key2);
    unsigned int cfuhash_generic_hash(cfuhash_fieldspec_t fields[], void* key);

    void free(void* ptr); /* stdlib's free */
""")

lib = cfuffi.verify(
    """
    #include <stdlib.h>
    #include "cfuhash.h"
    """,
    sources = ['shm/libcfu/cfuhash.c'],
    include_dirs = ['shm/libcfu'],
    #extra_compile_args = ['-g', '-O0'],
)
old_cwd.chdir()

class CNamespace(object):

    def __init__(self, lib, prefix):
        self._lib = lib
        PREFIX = prefix.upper()
        for key, value in lib.__dict__.iteritems():
            if key.startswith(prefix) or key.startswith(PREFIX):
                key = key[len(prefix):]
                setattr(self, key, value)

cfuhash = CNamespace(lib, 'cfuhash_')
