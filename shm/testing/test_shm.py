import py
import sys
import os
import cffi
import shm
from shm.sharedmem import sharedmem
from shm.list import ListType
from shm.dict import DictType
from shm.pyffi import PyFFI

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)

def exec_child(tmpdir, fn, *args):
    rootdir = py.path.local(shm.__file__).dirpath('..')
    
    filename = tmpdir.join(fn.__name__ + '.py')
    src = py.code.Source(fn)
    arglist = ', '.join(map(repr, args))
    call = '%s(%s)' % (fn.__name__, arglist)
    with filename.open('w') as f:
        f.write('import sys\n')
        f.write('sys.path.append(%s)\n' % repr(str(rootdir)))
        f.write(str(src))
        f.write('\n')
        f.write(call)
    #
    cmd = "%s %s" % (sys.executable, filename)
    #cmd = "gdb --args %s" % cmd
    ret = os.system(cmd)
    if ret != 0:
        raise ValueError("The child returned non-0 status")
    return True


def test_exec_child(tmpdir):
    def fn(a, b):
        assert a == b
    assert exec_child(tmpdir, fn, 10, 10)
    py.test.raises(ValueError, "exec_child(tmpdir, fn, 10, 11)")
            
            
def test_sharedmem(tmpdir):
    def child(path, str_addr):
        import cffi
        from shm.sharedmem import sharedmem
        #
        ffi = cffi.FFI()
        sharedmem.open_readonly(path)
        rawstr = ffi.cast('char*', str_addr)
        assert ffi.string(rawstr) == 'hello world'

    ffi = cffi.FFI()
    rawstr = sharedmem.new_string('hello world')
    str_addr = int(ffi.cast('long', rawstr))
    assert exec_child(tmpdir, child, PATH, str_addr)


def test_readonly_mem(tmpdir):
    def child(path, x_addr, should_segfault):
        import cffi
        from shm.sharedmem import sharedmem
        #
        ffi = cffi.FFI()
        sharedmem.open_readonly(path)
        x = ffi.cast('long*', x_addr)
        assert x[0] == 42
        if should_segfault:
            x[0] = 100 # BOOM

    ffi = cffi.FFI()
    x = sharedmem.new_array(ffi, 'long', 1)
    x[0] = 42
    x_addr = int(ffi.cast('long', x))
    assert exec_child(tmpdir, child, PATH, x_addr, False)
    py.test.raises(ValueError, "exec_child(tmpdir, child, PATH, x_addr, True)")


def test_gc_info(tmpdir):
    def child(path):
        from shm.sharedmem import sharedmem
        from shm import gclib
        #
        sharedmem.open_readonly(path)
        info = gclib.get_gc_info()
        assert info.magic == gclib.GC_INFO_MAGIC
        path = gclib.gcffi.string(info.path)
        assert path == '/cffi-shm-testing'

    assert exec_child(tmpdir, child, PATH)

def test_readwrite_mem(tmpdir):
    def child(path, x_addr, should_segfault):
        import cffi
        from shm.sharedmem import sharedmem
        #
        ffi = cffi.FFI()
        sharedmem.open_readonly(path)
        x = ffi.cast('long*', x_addr)
        assert x[0] == 42
        x[0] = 100

    ffi = cffi.FFI()
    x = sharedmem.new_array(ffi, 'long', 1, rw=True)
    x[0] = 42
    x_addr = int(ffi.cast('long', x))
    assert exec_child(tmpdir, child, PATH, x_addr, False)
    assert x[0] == 100


def test_list(tmpdir):
    def child(path, list_addr):
        import cffi
        from shm.sharedmem import sharedmem
        from shm.pyffi import PyFFI
        from shm.list import ListType
        #
        pyffi = PyFFI(cffi.FFI())
        sharedmem.open_readonly(path)
        LT = ListType(pyffi, 'long')
        lst = LT.from_pointer(list_addr)
        assert list(lst) == range(100)

    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    LT = ListType(pyffi, 'long')
    lst = LT(range(100))
    list_addr = int(ffi.cast('long', lst.lst))
    assert exec_child(tmpdir, child, PATH, list_addr)


def test_dict(tmpdir):
    def child(path, dict_addr):
        import cffi
        from shm.sharedmem import sharedmem
        from shm.pyffi import PyFFI
        from shm.dict import DictType
        #
        pyffi = PyFFI(cffi.FFI())
        DT = DictType(pyffi, 'const char*', 'long')
        sharedmem.open_readonly(path)
        d = DT.from_pointer(dict_addr)
        assert d['hello'] == 1
        assert d['world'] == 2
        assert sorted(d.keys()) == ['hello', 'world']

    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['hello'] = 1
    d['world'] = 2
    dict_addr = int(ffi.cast('long', d.ht))
    assert exec_child(tmpdir, child, PATH, dict_addr)


def test_dict_complex_key(tmpdir):
    def child(path, dict_addr):
        import cffi
        from shm.sharedmem import sharedmem
        from shm.pyffi import PyFFI
        #
        sharedmem.open_readonly(path)
        ffi = cffi.FFI()
        pyffi = PyFFI(ffi)
        ffi.cdef("""
            typedef struct {
                const char* name;
                const char* surname;
            } Person;
        """)
        Person = pyffi.struct('Person')
        PersonDict = pyffi.dict('Person*', 'long')
        d = PersonDict.from_pointer(dict_addr)
        assert d[Person('Hello', 'World')] == 1
        assert d[Person('Foo', 'Bar')] == 2

    ffi = cffi.FFI()
    pyffi = PyFFI(ffi)
    ffi.cdef("""
        typedef struct {
            const char* name;
            const char* surname;
        } Person;
    """)
    Person = pyffi.struct('Person')
    PersonDict = pyffi.dict('Person*', 'long')
    d = PersonDict()
    d[Person('Hello', 'World')] = 1
    d[Person('Foo', 'Bar')] = 2
    dict_addr = int(ffi.cast('long', d.ht))
    assert exec_child(tmpdir, child, PATH, dict_addr)
