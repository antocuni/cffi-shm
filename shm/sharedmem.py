import os
import cffi

# the python mmap module does not expose all the functionalities we need, in
# particular MAP_FIXED. So we need to build our own wrapper with cffi

mmapffi = cffi.FFI()
mmapffi.cdef("""
   static const int PROT_EXEC;
   static const int PROT_READ;
   static const int PROT_WRITE;
   static const int PROT_NONE;
   static const int MAP_SHARED;
   static const int MAP_PRIVATE;
   static const int MAP_FIXED;
   #define MAP_FAILED ...

   void *mmap(void *addr, size_t length, int prot, int flags, int fd, size_t offset);
   int munmap(void *addr, size_t length);
""")

lib = mmapffi.verify("#include <sys/mman.h>")

class SharedMemory(object):
    def __init__(self, fd, addr, size):
        self.fd = fd
        self.addr = addr
        self.size = size

    @classmethod
    def open(cls, path, base_address, size):
        fd = os.open(path, os.O_RDWR)
        base_address = mmapffi.cast("void*", base_address)
        prot  = lib.PROT_WRITE | lib.PROT_READ
        flags = lib.MAP_SHARED | lib.MAP_FIXED
        addr = lib.mmap(base_address, size, prot, flags, fd, 0)
        if addr == lib.MAP_FAILED:
            errno = mmapffi.errno
            raise OSError(os.strerror(errno), errno)
        assert addr == base_address
        return cls(fd, addr, size)

    def close(self):
        lib.munmap(self.addr, self.size)
        os.close(self.fd)
