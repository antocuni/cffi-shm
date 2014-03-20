import py
import cffi

ROOTDIR = py.path.local(__file__).dirpath('..')
GCDIR = ROOTDIR.join('GC')

# this is a bit hackish, but we need to use paths which are relative to the
# root of the package: when we run setup.py install, cffi builds an extension
# whose checksum depends on the arguments passed to verify, including
# SOURCES. If we use absolute paths, the checksum will change after the
# installation and it'll try to rebuild it (failing, because it won't find the
# .h and .c files). By using relative paths, the checksum doesn't change and
# we can safely use the cffi module built during the install.
#
# To be more robust, we ensure that the cwd is ROOTDIR.

old_cwd = ROOTDIR.chdir()

gcffi = cffi.FFI()
gcffi.cdef("""
    bool GC_init(const char* path);
    void* GC_get_memory(void);
    void* GC_malloc(size_t size);
    void* GC_realloc(void* ptr, size_t size);
    void GC_free(void *ptr);
    void GC_collect(void);
    long GC_total_collections(void);
    bool GC_root(void* ptr, size_t size);
    void GC_enable(void);
    void GC_disable(void);

    /* these are needed because AFAIK there is no other way to get the raw
       address of the C functions (unless I declare the functions as pointers
       as suggested by cffi docs, but in that case it's slower to call them)
    */
    typedef void* (*malloc_fn)(size_t);
    typedef void (*free_fn)(void*);
    malloc_fn get_GC_malloc(void);
    free_fn get_GC_free(void);

    char *strncpy(char *dest, const char *src, size_t n);
""")

lib = gcffi.verify(
    """
    #include <string.h>
    #include "gc.h"

    typedef void* (*malloc_fn)(size_t);
    typedef void (*free_fn)(void*);
    malloc_fn get_GC_malloc(void) { return GC_malloc; }
    free_fn   get_GC_free(void)   { return GC_free; }
    """,
    sources = ['GC/gc.c'],
    include_dirs = ['GC'],
    extra_compile_args = ['--std=gnu99'],
)
old_cwd.chdir()

def init(path):
    lib.GC_init(path)

def new(ffi, t, root=False):
    ptr = lib.GC_malloc(ffi.sizeof(t))
    if ptr == ffi.NULL:
        raise MemoryError
    res = ffi.cast(t + "*", ptr)
    if root:
        roots.add(res)
    return res

def new_array(ffi, t, n, root=False):
    ptr = lib.GC_malloc(ffi.sizeof(t) * n)
    res = ffi.cast("%s[%d]" % (t, n) , ptr)
    if root:
        roots.add(res)
    return res

def new_string(s, root=False):
    size = len(s)+1
    ptr = lib.GC_malloc(size)
    # XXX: this does one extra copy, because s is copied to a temp buffer to
    # pass to strncpy. I don't know how to avoid it, though
    lib.strncpy(ptr, s, len(s))
    if root:
        roots.add(res)
    return gcffi.cast('char*', ptr)

def realloc_array(ffi, t, ptr, n):
    ptr = lib.GC_realloc(ptr, ffi.sizeof(t) * n)
    return ffi.cast("%s[%d]" % (t, n) , ptr)


collect = lib.GC_collect
total_collections = lib.GC_total_collections
enable = lib.GC_enable
disable = lib.GC_disable

class RootCollection(object):
    """
    For now we allow only a fixed number of roots, up to 512.  In the future,
    we can make it smarter to grow/shrink automatically.
    """
    def __init__(self):
        self.n = 0
        self.maxroots = 512
        self.mem = gcffi.new('void*[]', self.maxroots)
        lib.GC_root(self.mem, self.maxroots)

    def add(self, ptr):
        self.mem[self.n] = ptr
        self.n += 1

roots = RootCollection()


class Disabled(object):
    def __enter__(self):
        disable()

    def __exit__(self, exctype, excvalue, tb):
        enable()

disabled = Disabled()
