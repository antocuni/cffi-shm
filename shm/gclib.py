import py
import cffi

ROOT = py.path.local(__file__).dirpath('..')
GCDIR = ROOT.join('GC')

# this is a bit hackish, but we need to use paths which are relative to the
# root of the package: when we run setup.py install, cffi builds an extension
# whose checksum depends on the arguments passed to verify, including
# SOURCES. If we use absolute paths, the checksum will change after the
# installation and it'll try to rebuild it (failing, because it won't find the
# .h and .c files). By using relative paths, the checksum doesn't change and
# we can safely use the cffi module built during the install.
#
# To be more robust, we ensure that the cwd is ROOT.

old_cwd = ROOT.chdir()

gcffi = cffi.FFI()
gcffi.cdef("""
    bool GC_init(const char* path);
    void* GC_get_memory(void);
    void* GC_malloc(size_t size);
    void GC_collect(void);
    bool GC_root(void* ptr, size_t size);
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

def new(ffi, t):
    ptr = lib.GC_malloc(ffi.sizeof(t))
    return ffi.cast(t + "*", ptr)

collect = lib.GC_collect
