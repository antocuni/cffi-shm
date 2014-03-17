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
    void GC_collect(void);
    bool GC_root(void* ptr, size_t size);
    void GC_enable(void);
    void GC_disable(void);
""")

lib = gcffi.verify(
    """
    #include "gc.h"
    """,
    sources = ['GC/gc.c'],
    include_dirs = ['GC'],
    extra_compile_args = ['--std=gnu99'],
)

def init(path):
    lib.GC_init(path)

def new(ffi, t, root=False):
    ptr = lib.GC_malloc(ffi.sizeof(t))
    res = ffi.cast(t + "*", ptr)
    if root:
        roots.add(res)
    return res

collect = lib.GC_collect
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

