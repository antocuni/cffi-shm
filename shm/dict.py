import py
import cffi

ROOTDIR = py.path.local(__file__).dirpath('..')
GCDIR = ROOTDIR.join('GC')
old_cwd = ROOTDIR.chdir()

dictffi = cffi.FFI()
dictffi.cdef("""
    typedef ... cfuhash_table_t;
    cfuhash_table_t* cfuhash_new(void);
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
)
old_cwd.chdir()
