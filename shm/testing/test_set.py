import py
from shm import gclib
from shm.testing.test_dict import ffi, pyffi
gclib.init('/cffi-shm-testing')

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
