import time
import errno
from shm.pthread import pthread
from shm.sharedmem import sharedmem

def _new_mutex():
	attr = pthread.ffi.new('pthread_mutexattr_t*')
	pthread.checked.mutexattr_init(attr)
	pthread.checked.mutexattr_setpshared(attr, pthread.PROCESS_SHARED)
	pthread.checked.mutexattr_setrobust_np(attr, pthread.MUTEX_ROBUST_NP)
	pthread.checked.mutexattr_settype(attr, pthread.MUTEX_RECURSIVE)
	#
	mutex = sharedmem.new(pthread.ffi, 'pthread_mutex_t*', rw=True)
	pthread.checked.mutex_init(mutex, attr)
	pthread.checked.mutexattr_destroy(attr)
	return mutex


class ShmLock(object):

    def __init__(self):
        self.mutex = _new_mutex()
        self.owning = True
    
    @classmethod
    def from_pointer(cls, addr):
        self = cls.__new__(cls)
        self.mutex = pthread.ffi.cast('pthread_mutex_t*', addr)
        self.owning = False
        return self

    def as_cdata(self):
        return self.mutex

    def __del__(self):
        if self.owning:
            pthread.checked.mutex_destroy(self.mutex)

    def acquire(self):
        ret = pthread.mutex_lock(self.mutex)
        if ret == pthread.EOWNERDEAD:
            # the slave process has died. Let's make the mutex consistent
            # again
            pthread.mutex_consistent_np(self.mutex)
            pass
        else:
            assert ret == 0

    def release(self):
        pthread.checked.mutex_unlock(self.mutex)
        # the sleep is necessary to force to reschedule the process, and give
        # immediately the other processes a chance to get the mutex
        time.sleep(0)

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_value, tb):
        self.release()
