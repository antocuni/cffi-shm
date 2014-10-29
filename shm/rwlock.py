import time
import errno
from cffi import FFI
from shm.pthread import pthread
from shm.sharedmem import sharedmem
from shm.lock import _new_mutex

ffi = FFI()
ffi.include(pthread.ffi)
ffi.cdef("""
    typedef struct {
        pthread_mutex_t *wr_mutex;
        pthread_mutex_t *rdcount_mutex;
        int rdcount;
    } rwlock_t;
""")

class ShmRWLock(object):

    def __init__(self):
        self.rwlock = sharedmem.new(ffi, 'rwlock_t*', rw=True)
        self.rwlock.wr_mutex = _new_mutex()
        self.rwlock.rdcount_mutex = _new_mutex()
        self.owning = True

    @classmethod
    def from_pointer(cls, addr):
        self = cls.__new__(cls)
        self.rwlock = ffi.cast('rwlock_t*', addr)
        self.owning = False
        return self

    def as_cdata(self):
        return self.rwlock

    def __del__(self):
        if self.owning:
            pthread.checked.mutex_destroy(self.rwlock.wr_mutex)
            pthread.checked.mutex_destroy(self.rwlock.rdcount_mutex)

    def wr_acquire(self):
        ret = pthread.mutex_lock(self.rwlock.wr_mutex)
        assert ret == 0 # XXX, handle EOWNERDEAD

    def wr_release(self):
        pthread.checked.mutex_unlock(self.rwlock.wr_mutex)
        # the sleep is necessary to force to reschedule the process, and give
        # immediately the other processes a chance to get the mutex
        time.sleep(0)

