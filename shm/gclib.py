import os.path
import py
import cffi
from shm.util import cffi_typeof

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
    bool GC_init(const char* path);    /* GC fully initialized */
    bool GC_open(const char* parth);   /* GC memory mmaped, but cannot allocate */
    bool GC_isptr(void* ptr);
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

    const int PROT_NONE;
    const int PROT_READ;
    const int PROT_WRITE;
    const int PROT_EXEC;
    int mprotect(void *addr, size_t len, int prot);

    typedef struct {
        long magic;
        const char* path;
        void* rwmem;
        size_t rwmem_size;
    } gclib_info_t;
""")

## import distutils.log
## distutils.log.set_verbosity(1)

# if you want GDB to be able to locate symbols, you need an absolute
# path. However, to distribute the library we need a relative one (see the big
# comment above). Uncomment the second line for development if you need debug
# symbols.
GC_path = 'GC'
#GC_path = os.path.abspath(GC_path)

lib = gcffi.verify(
    """
    #include <string.h>
    #include <sys/mman.h>
    #include "gc.h"

    typedef void* (*malloc_fn)(size_t);
    typedef void (*free_fn)(void*);
    malloc_fn get_GC_malloc(void) { return GC_malloc_noinline; }
    free_fn   get_GC_free(void)   { return GC_free_noinline; }
    typedef struct {
        long magic;
        const char* path;
        void* rwmem;
        size_t rwmem_size;
    } gclib_info_t;

    """,
    include_dirs = ['GC'],
    #extra_compile_args = ['-g', '-O0'],
    extra_link_args = ['-Wl,-rpath,%s' % GC_path, '-LGC', '-lshmgc', '-lrt'],
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
    if path.count('/') != 1:
        raise OSError('%r should contain exactly one slash' % path)
    ret = lib.GC_init(path)
    if not ret:
        raise OSError('Failed to initialized the shm GC')
    #
    if init.gc_info is None:
        init.gc_info = allocate_gc_info(path) # to keep it alive
init.gc_info = None


GC_INFO_ADDRESS = 0x1100000000
GC_INFO_MAGIC = 0x1234ABCDEF
RW_MEM_SIZE = 1024*1024 # 1 MB
#
def allocate_gc_info(path):
    gc_info = new(gcffi, 'gclib_info_t*')
    gc_info_addr = gcffi.cast('long', gc_info)
    if int(gc_info_addr) != GC_INFO_ADDRESS:
        # if this happens, it probably means that the size of gc_struct has
        # changed and the GC allocates it in a new bucket. Simply change the
        # value of GC_INFO_ADDRESS accordingly
        raise ValueError("The gc_info struct was supposed to be allocated "
                         "at the addres 0x%x" % GC_INFO_ADDRESS)
    gc_info.magic = GC_INFO_MAGIC
    gc_info.path = new_string(path, root=False)
    #
    # allocate a RW area
    gc_info.rwmem = lib.GC_malloc(RW_MEM_SIZE)
    gc_info.rwmem_size = RW_MEM_SIZE
    rw_allocator.init(gc_info.rwmem, gc_info.rwmem_size)
    return gc_info

def get_gc_info():
    return gcffi.cast('gclib_info_t*', GC_INFO_ADDRESS)


def open_readonly(path):
    if path.count('/') != 1:
        raise OSError('%r should contain exactly one slash' % path)
    ret = lib.GC_open(path)
    if not ret:
        raise OSError('Failed to open the shm GC')
    #
    # now, we need to enable writing to the RW part of the memory
    gc_info = get_gc_info()
    if gc_info.magic != GC_INFO_MAGIC:
        raise ValueError("The gc_info global does not seem to be at the address 0x%x, "
                         "or it has been corrupted" % GC_INFO_ADDRESS)
    ret = lib.mprotect(gc_info.rwmem, gc_info.rwmem_size, lib.PROT_READ | lib.PROT_WRITE)
    if ret != 0:
        raise OSError("mprotect failed: error code: %d" % ret)

def _malloc(size, rw):
    if rw:
        return rw_allocator.malloc(size)
    else:
        return lib.GC_malloc(size)

def new(ffi, t, root=True, rw=False):
    ctype = cffi_typeof(ffi, t)
    if ctype.kind != 'pointer':
        raise TypeError("Expected a pointer, got '%s'" % t)
    ptr = _malloc(ffi.sizeof(ctype.item), rw)
    if ptr == ffi.NULL:
        raise MemoryError
    res = ffi.cast(ctype, ptr)
    if root:
        res = roots.add(ffi, res, ctype)
    return res

def new_array(ffi, t, n, root=True, rw=False):
    ptr = _malloc(ffi.sizeof(t) * n, rw)
    res = ffi.cast("%s[%d]" % (t, n) , ptr)
    if root:
        res = roots.add(ffi, res, '%s[]' % t)
    return res

def new_string(s, root=True):
    size = len(s)+1
    ptr = lib.GC_malloc(size)
    # XXX: this does one extra copy, because s is copied to a temp buffer to
    # pass to strncpy. I don't know how to avoid it, though
    lib.strncpy(ptr, s, size)
    ptr = gcffi.cast('char*', ptr)
    if root:
        ptr = roots.add(gcffi, ptr, '<string>')
    return ptr

def realloc_array(ffi, t, ptr, n):
    ptr = lib.GC_realloc(ptr, ffi.sizeof(t) * n)
    return ffi.cast("%s[%d]" % (t, n) , ptr)


collect = lib.GC_collect
total_collections = lib.GC_total_collections
enable = lib.GC_enable
disable = lib.GC_disable
isptr = lib.GC_isptr

class GcRootCollection(object):
    """
    For now we allow only a fixed number of roots. In the future, we can make
    it smarter to grow/shrink automatically.
    """
    def __init__(self, maxroots):
        self.n = 0
        self.maxroots = maxroots
        self.mem = gcffi.new('void*[]', self.maxroots)
        self.extrainfo = [None] * self.maxroots
        size = self.maxroots * gcffi.sizeof('void*')
        lib.GC_root(self.mem, size)

    def _add(self, ptr, einfo):
        i = self.n
        while True:
            if self.mem[i] == gcffi.NULL:
                break
            i = (i+1) % self.maxroots
            if i == self.n:
                raise ValueError, 'No more space for GC roots'

        self.n = i
        return GcRoot(self, i, ptr, einfo)

    def add(self, ffi, ptr, einfo='<unknown>'):
        root = self._add(ptr, einfo)
        return ffi.gc(ptr, root.clear)


class GcRoot(object):
    def __init__(self, collection, i, ptr, einfo):
        self.collection = collection
        self.i = i
        self.collection.mem[i] = ptr
        self.collection.extrainfo[i] = einfo

    def clear(self, ptr):
        self.collection.mem[self.i] = gcffi.NULL
        self.collection.extrainfo[self.i] = None

roots = GcRootCollection(2048)


class Disabled(object):
    def __enter__(self):
        disable()

    def __exit__(self, exctype, excvalue, tb):
        enable()

disabled = Disabled()

class DummyAllocator(object):
    """
    Very dummy allocator to manage the Read-Write memory.

    It simply bumps a pointer until we finish the space. The allocated memory
    is never freed. It is not a problem because RW memory should be used very
    carefully, ideally only for pthread_mutexes, and you should not need many
    of them.

    If you need more space, you can simply augment RW_MEM_SIZE.
    """
    
    def __init__(self):
        self.start_mem = None

    def init(self, mem, size):
        self.start_mem = mem
        self.end_mem = mem+size
        self.last_mem = mem

    def malloc(self, size):
        assert self.start_mem is not None
        mem = self.last_mem
        if mem+size > self.end_mem:
            return gcffi.NULL
        self.last_mem += size
        return mem
        
rw_allocator = DummyAllocator()

def protect():
    """
    For debugging purpose. Temporarily mark the GC memory as read-only, to get
    a segfault in case anyone tries to write when it's not supposed to.
    """
    mem = lib.GC_get_memory()
    size = lib.GC_get_memsize()
    ret = lib.mprotect(mem, size, lib.PROT_READ)

def unprotect():
    """
    For debugging purpose. Undo the effect of protect()
    """
    mem = lib.GC_get_memory()
    size = lib.GC_get_memsize()
    ret = lib.mprotect(mem, size, lib.PROT_READ | lib.PROT_WRITE)
