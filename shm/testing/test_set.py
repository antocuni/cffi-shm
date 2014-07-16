import py
from shm.sharedmem import sharedmem
from shm.testing.test_dict import pyffi
sharedmem.init('/cffi-shm-testing')

def test_SetType(pyffi):
    ST = pyffi.set('long')
    assert repr(ST) == '<shm type set [long]>'
    
def test_add_contains(pyffi):
    ST = pyffi.set('const char*')
    s = ST()
    s.add("foo")
    s.add("bar")
    assert "foo" in s
    assert "bar" in s
    assert "foobar" not in s

def test___iter__(pyffi):
    ST = pyffi.set('const char*')
    s = ST()
    s.add("foo")
    s.add("bar")
    lst = sorted(list(s))
    assert lst == ["bar", "foo"]

def test_remove(pyffi):
    ST = pyffi.set('const char*')
    s = ST()
    s.add("foo")
    s.add("bar")
    s.remove("foo")
    assert list(s) == ["bar"]
    #
    py.test.raises(KeyError, "s.remove('foo')")

def test_discard(pyffi):
    ST = pyffi.set('const char*')
    s = ST()
    s.add("foo")
    s.add("bar")
    s.discard("foo")
    assert list(s) == ["bar"]
    #
    s.discard("foo") # check it does not raise

def test_len(pyffi):
    ST = pyffi.set('const char*')
    s = ST()
    assert len(s) == 0
    s.add("foo")
    s.add("bar")
    assert len(s) == 2

def test_init(pyffi):
    ST = pyffi.set('const char*')
    s = ST(['foo', 'bar'])
    assert len(s) == 2
    assert sorted(list(s)) == ['bar', 'foo']
