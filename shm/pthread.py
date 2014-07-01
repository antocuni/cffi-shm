from cffi import FFI
from shm.util import CNamespace, Checked

ffi = FFI()
ffi.cdef("""
    const int PTHREAD_PROCESS_PRIVATE;
    const int PTHREAD_PROCESS_SHARED;
    const int PTHREAD_MUTEX_STALLED_NP;
    const int PTHREAD_MUTEX_ROBUST_NP;
    const int PTHREAD_MUTEX_RECURSIVE;
    const int EOWNERDEAD;

    typedef struct { ...; } pthread_mutex_t;
    typedef struct { ...; } pthread_mutexattr_t;

    int pthread_mutex_init(pthread_mutex_t *restrict mutex,
                           const pthread_mutexattr_t *restrict attr);
    int pthread_mutex_destroy(pthread_mutex_t *mutex);
    int pthread_mutex_lock(pthread_mutex_t *mutex);
    int pthread_mutex_unlock(pthread_mutex_t *mutex);

    int pthread_mutexattr_init(pthread_mutexattr_t *attr);
    int pthread_mutexattr_destroy(pthread_mutexattr_t *attr);
    int pthread_mutexattr_setpshared(pthread_mutexattr_t *attr, int pshared);
    int pthread_mutexattr_setrobust_np(pthread_mutexattr_t *attr, int robust);
    int pthread_mutexattr_settype(pthread_mutexattr_t *attr, int type);

    int pthread_mutex_consistent_np(pthread_mutex_t *mutex);
""")



lib = ffi.verify(
    "#include <pthread.h>",
    extra_link_args = ['-lpthread']
    )

pthread = CNamespace(lib, 'pthread_')
pthread.EOWNERDEAD = lib.EOWNERDEAD
pthread.ffi = ffi
pthread.checked = Checked(pthread)
