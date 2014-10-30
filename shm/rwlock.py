import time
import fcntl
import tempfile
from cffi import FFI
from shm.sharedmem import sharedmem
ffi = FFI()

class ShmRWLock(object):
    """
    Cross-process Read/Write Lock based on fnctl.flock
    """

    def __init__(self):
        self._f = tempfile.NamedTemporaryFile(suffix='.lock', prefix='shm')
        self.lockpath = sharedmem.new_string(self._f.name)
        self.fd = self._f.file.fileno()

    @classmethod
    def from_pointer(cls, addr):
        self = cls.__new__(cls)
        self.lockpath = ffi.cast('const char*', addr)
        path = ffi.string(self.lockpath)
        self._f = open(path)
        self.fd = self._f.fileno()
        return self

    def as_cdata(self):
        return self.lockpath

    def wr_acquire(self):
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def wr_release(self):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        # the sleep is necessary to force to reschedule the process, and give
        # immediately the other processes a chance to get the mutex
        time.sleep(0)

    def rd_acquire(self):
        fcntl.flock(self.fd, fcntl.LOCK_SH)

    def rd_release(self):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
