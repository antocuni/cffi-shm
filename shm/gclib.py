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
    size_t GC_get_memsize(void);
    void* GC_malloc(size_t size);
    void* GC_realloc(void* ptr, size_t size);
    void GC_free(void *ptr);
    void GC_collect(void);
    long GC_total_collections(void);
    bool GC_root(void* ptr, size_t size);
    void GC_enable(void);
    void GC_disable(void);

    /* The CFFI docs suggest to declare GC_malloc_noinline and
       GC_free_noinline as function pointers. However, it seems we get an
       address which is different than the actual one of the functions inside
       the library. Use this hack instead.
    */
    typedef void* (*malloc_fn)(size_t);
    typedef void (*free_fn)(void*);
    malloc_fn get_GC_malloc(void);
    free_fn get_GC_free(void);

    char *strncpy(char *dest, const char *src, size_t n);
""")

## import distutils.log
## distutils.log.set_verbosity(1)
lib = gcffi.verify(
    """
    #include <string.h>
    #include "gc.h"

    typedef void* (*malloc_fn)(size_t);
    typedef void (*free_fn)(void*);
    malloc_fn get_GC_malloc(void) { return GC_malloc_noinline; }
    free_fn   get_GC_free(void)   { return GC_free_noinline; }
    """,
    include_dirs = ['GC'],
    #extra_compile_args = ['-g', '-O0'],
    extra_link_args = ['-Wl,-rpath,GC', '-LGC', '-lshmgc',],
)
old_cwd.chdir()

def sanity_check():
    # check that GC_malloc()&co. are placed immediately after the GC data
    gc_area_start = int(gcffi.cast('long', lib.GC_get_memory()))
    gc_area_end = gc_area_start + lib.GC_get_memsize()
    GC_malloc_addr = int(gcffi.cast('long', lib.get_GC_malloc()))
    offset = GC_malloc_addr - gc_area_end
    # if the offset is >1MB, it probably means that the lib was placed
    # somewhere else
    assert 0 < offset < 1024**2, 'The GC library does not seem to be at the proper location in memory. Check the linker script.'

sanity_check()


def init(path):
    shm_dir = py.path.local(path).dirpath()
    if shm_dir.check(exists=False):
        raise OSError('The directory %s does not seem to exist' % shm_dir)
    lib.GC_init(path)

def new(ffi, t, root=False):
    ctype = ffi.typeof(t)
    if ctype.kind != 'pointer':
        raise TypeError("Expected a pointer, got '%s'" % t)
    ptr = lib.GC_malloc(ffi.sizeof(ctype.item))
    if ptr == ffi.NULL:
        raise MemoryError
    res = ffi.cast(ctype, ptr)
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
    lib.strncpy(ptr, s, size)
    if root:
        roots.add(ptr)
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
        self.reinit()

    def reinit(self):
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
