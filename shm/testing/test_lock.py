import time
import cffi
from shm.sharedmem import sharedmem
from shm.lock import ShmLock
from shm.testing.util import SubProcess, exec_child

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)

def test_simple_lock(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.lock import ShmLock
        from shm.testing.util import assert_elapsed_time
        #
        sharedmem.open_readonly(path)
        lock = ShmLock.from_pointer(lock_addr)
        with assert_elapsed_time(0.3, 0.5):
            # the lock is owned by the parent for 0.5 seconds
            lock.acquire()
            lock.release()

    ffi = cffi.FFI()
    lock = ShmLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))
    with SubProcess() as p:
        p.background(tmpdir, child, PATH, lock_addr)
        lock.acquire()
        time.sleep(0.5)
        lock.release()


def test_robust_lock(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.lock import ShmLock
        #
        sharedmem.open_readonly(path)
        lock = ShmLock.from_pointer(lock_addr)
        lock.acquire()
        # note: we do NOT release the lock, but this process dies anyway

    ffi = cffi.FFI()
    lock = ShmLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))
    assert exec_child(tmpdir, child, PATH, lock_addr)
    #
    # now the child has acquired but not released the lock. We should be able
    # to acquire it anyway, because we handle EOWNERDEAD
    lock.acquire()
    lock.release()
    #
    # now, we check that we made the lock consistent again
    lock.acquire()
    lock.release()


def test_recursive_lock():
    lock = ShmLock()
    lock.acquire()
    lock.acquire()
    lock.release()
    lock.release()
    
