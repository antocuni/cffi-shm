import time
import threading
import cffi
from shm.sharedmem import sharedmem
from shm.lock import ShmLock
from shm.testing.test_shm import exec_child

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)

def test_simple_lock(tmpdir):
    def child(path, lock_addr):
        import time
        from shm.sharedmem import sharedmem
        from shm.lock import ShmLock
        #
        sharedmem.open_readonly(path)
        lock = ShmLock.from_pointer(lock_addr)
        a = time.time()
        # at this point, the lock is owned by the thread t. It will be
        # released after 0.5 secondsa
        lock.acquire()
        b = time.time()
        lock.release()
        diff = abs(b-a)
        # we check that the lock has been owned by ~0.5 seconds
        assert 0.3 < diff < 0.5

    def acquire_and_release(lock):
        import sys
        lock.acquire()
        time.sleep(0.5)
        lock.release()

    ffi = cffi.FFI()
    lock = ShmLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))
    #
    # we start:
    # 1) a thread which locks, wait 0.5 secs, release
    # 2) a process which measure how much time has to wait to aquire the lock
    t = threading.Thread(target=acquire_and_release, args = (lock,))
    t.start()
    assert exec_child(tmpdir, child, PATH, lock_addr)
    t.join()


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
    
