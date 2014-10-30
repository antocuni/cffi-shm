import time
import fcntl
import tempfile
from cffi import FFI
from shm.sharedmem import sharedmem
ffi = FFI()

class ShmRWLock(object):
    """
    Cross-process Read/Write Lock based on fnctl.flock

    Note that this lock is safe only for inter-PROCESS locking. It might not
    work properly between two threads belonging to the same process.

    Also, it stores some data directly on the Python instance; so, it is not
    safe two have two different Python instances referring to the same
    underlying rwlock (which could happen e.g. if you call from_pointer()
    twice)
    """

    wrcount = 0
    rdcount = 0

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
        if self.wrcount == 0:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.wrcount += 1

    def wr_release(self):
        self.wrcount -= 1
        if self.wrcount == 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        # the sleep is necessary to force to reschedule the process, and give
        # immediately the other processes a chance to get the mutex
        time.sleep(0)

    def rd_acquire(self):
        if self.rdcount == 0:
            fcntl.flock(self.fd, fcntl.LOCK_SH)
        self.rdcount += 1

    def rd_release(self):
        self.rdcount -= 1
        if self.rdcount == 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        # the sleep is necessary to force to reschedule the process, and give
        # immediately the other processes a chance to get the mutex
        time.sleep(0)
