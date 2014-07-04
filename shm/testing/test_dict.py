import py
import pytest
import cffi
from shm.sharedmem import sharedmem
from shm.dict import DictType
from shm.pyffi import PyFFI
sharedmem.init('/cffi-shm-testing')

@pytest.fixture
def pyffi():
    return PyFFI(cffi.FFI())

def test_DictType(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    assert repr(DT) == '<shm type dict [const char*: long]>'

def test_getsetitem(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    py.test.raises(KeyError, "d['hello']")
    d['hello'] = 42
    assert d['hello'] == 42

def test_len(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    assert len(d) == 0
    d['hello'] = 42
    assert len(d) == 1
    d['world'] = 43
    assert len(d) == 2

def test_strvalue(pyffi):
    DT = DictType(pyffi, 'const char*', 'const char*')
    d = DT()
    d['hello'] = 'world'
    assert d['hello'] == 'world'

def test_contains(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    assert 'hello' not in d
    d['hello'] = 42
    assert 'hello' in d

def test_get(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    assert d.get('hello') is None
    assert d.get('hello', 123) == 123
    d['hello'] = 42
    assert d.get('hello') == 42

def test___delitem__(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['hello'] = 42
    assert 'hello' in d
    del d['hello']
    assert 'hello' not in d
    py.test.raises(KeyError, "del d['foo']")

def test_keys_values_items(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    d['baz'] = 3
    #
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']
    #
    values = d.values()
    assert sorted(values) == [1, 2, 3]
    #
    items = d.items()
    assert sorted(items) == [('bar', 2), ('baz', 3), ('foo', 1)]

def test___iter__(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    d['baz'] = 3
    assert sorted(list(d)) == ['bar', 'baz', 'foo']

def test_update(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d.update({'bar': 1, 'baz': 2})
    d.update([('foo', 3)])
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']

def test_pop(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['foo'] = 1
    d['bar'] = 2
    assert d.pop('foo') == 1
    assert 'foo' not in d
    py.test.raises(KeyError, "d.pop('foo')")
    assert d.pop('foo', 42) == 42


def test_ctor(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT({'bar': 1, 'baz': 2, 'foo': 3})
    keys = d.keys()
    assert sorted(keys) == ['bar', 'baz', 'foo']


def test_from_pointer(pyffi):
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT()
    d['hello'] = 1
    d['world'] = 2
    ptr = pyffi.ffi.cast('void*', d.ht)
    #
    d2 = DT.from_pointer(ptr)
    assert d2['hello'] == 1
    assert d2['world'] == 2

def test_long_key(pyffi):
    DT = DictType(pyffi, 'long', 'long')
    d = DT()
    d[10] = 20
    d[20] = 40
    assert d[10] == 20
    assert d[20] == 40

def test_double_key_values(pyffi):
    DT = DictType(pyffi, 'long', 'double')
    d = DT()
    d[10.1] = 20.3
    d[20.2] = 40.5
    assert d[10.1] == 20.3
    assert d[20.2] == 40.5

def test_key_struct_byval(pyffi):
    # first: we use struct by value as keys, easy case
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            char first_name[20];
            char last_name[20];
        } FullName;
    """)

    class FullName(pyffi.struct('FullName')):
        # this is needed for 'sorted' below
        def __cmp__(self, other):
            return cmp(self._key(), other._key())

    antocuni = FullName('Antonio', 'Cuni')
    antocuni2 = FullName('Antonio', 'Cuni')
    wrongname = FullName('Antonio', 'Foobar')

    DT = DictType(pyffi, 'FullName', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d[antocuni2] == 1
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]


def test_key_struct_with_pointers(pyffi):
    # second: we use struct by value as keys: the keys are compared shallowly,
    # so if they contains two different pointers to the same string, they are
    # considered unequal
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            const char* first_name;
            const char* last_name;
        } FullName;
    """)

    class FullName(pyffi.struct('FullName')):
        # this is needed for 'sorted' below
        def __cmp__(self, other):
            return cmp(self._key(), other._key())

    antocuni = FullName('Antonio', 'Cuni')
    antocuni2 = FullName('Antonio', 'Cuni')
    wrongname = FullName('Antonio', 'Foobar')

    DT = DictType(pyffi, 'FullName', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d.get(antocuni2) is None
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]
    #
    # ------------------------------------
    #
    # third: keys are pointers to a struct, and comparison is done using the
    # "fieldspec", i.e. it's a deep comparison
    #
    DT = DictType(pyffi, 'FullName*', 'long')
    d = DT()
    d[antocuni] = 1
    d[wrongname] = 2
    assert d[antocuni] == 1
    assert d[antocuni2] == 1
    assert d[wrongname] == 2
    #
    keys = sorted(d.keys())
    assert keys == [antocuni, wrongname]

def test_keys_list_of_strings(pyffi):
    LT = pyffi.list('const char*', immutable=True, cname='LT')
    DT = pyffi.dict('LT*', 'long')
    a = LT(['foo', 'bar'])
    b = LT(['foo', 'bar'])
    c = LT(['foo', 'hello'])
    d = DT()
    d[a] = 42
    assert d[a] == 42
    assert d[b] == 42
    assert c not in d

def test_defaultdict(pyffi):
    DT = pyffi.defaultdict('const char*', 'long', lambda: 42)
    d = DT()
    assert d['hello'] == 42
    assert 'hello' in d
    assert 'foo' not in d
    assert d.get('foo') is None

def test_defaultdict_struct_keys(pyffi):
    ffi = pyffi.ffi
    ffi.cdef("""
        typedef struct {
            long x;
            long y;
        } Point;
    """)

    Point = pyffi.struct('Point')
    DT = pyffi.defaultdict('Point', 'long', lambda: 42)
    d = DT()
    p = Point(1, 2)
    assert d[p] == 42

def test_defaultdict_pop(pyffi):
    DT = pyffi.defaultdict('const char*', 'long', lambda: 42)
    d = DT()
    py.test.raises(KeyError, "d.pop('hello')")
    assert d['hello'] == 42
    d.pop('hello') == 42
    py.test.raises(KeyError, "d.pop('hello')")
