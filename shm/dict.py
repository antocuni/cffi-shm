import py
import cffi
from shm.sharedmem import sharedmem
from shm.pyffi import AbstractGenericType
from shm.libcfu import cfuffi, cfuhash
from shm.util import cffi_is_string, cffi_is_struct_ptr, cffi_is_struct


class DictType(AbstractGenericType):
    def __init__(self, pyffi, keytype, valuetype, default_factory=None):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.nocopy = False # by default, keys are copied
        self.key_fieldspec = None
        self.keytype = keytype
        self.valuetype = valuetype
        self.default_factory = default_factory
        if cffi_is_string(self.ffi, keytype):
            self.keysize = self.ffi.cast('size_t', -1)
        elif cffi_is_struct_ptr(self.ffi, keytype):
            self.nocopy = True
            self.keysize = self.ffi.sizeof(keytype)
            pytype = pyffi.pytypeof(keytype)
            if pytype.__fieldspec__ is None:
                raise TypeError, 'Non-immutable shm dict key: %s' % pytype
            self.key_fieldspec = pytype.__fieldspec__
        elif cffi_is_struct(self.ffi, keytype):
            self.nocopy = True
            self.keysize = self.ffi.sizeof(keytype)
        else: # primitive types
            # by setting keysize to 0, we compare the void* pointers directly,
            # not their content. Note that 'long' and 'double' keys will be
            # casted to void*, and we surely don't want to dereference them :)            
            self.nocopy = True
            self.keysize = 0
        #
        self.keyconverter = pyffi.get_converter(keytype, allow_structs_byval=True)
        self.valueconverter = pyffi.get_converter(valuetype)

    def __repr__(self):
        return '<shm type dict [%s: %s]>' % (self.keytype, self.valuetype)

    def __call__(self, init=None, root=True):
        with sharedmem.gc_disabled:
            ptr = cfuhash.new_with_malloc_fn(sharedmem.get_GC_malloc(),
                                             sharedmem.get_GC_free())
        if self.nocopy:
            cfuhash.set_flag(ptr, cfuhash.NOCOPY_KEYS)
        if self.key_fieldspec:
            cfuhash.set_key_fieldspec(ptr, self.key_fieldspec)
        #
        if root:
            ptr = sharedmem.roots.add(cfuffi, ptr)
        # NOTE: it is very important that we call _from_ht and not
        # from_pointer, because the latter does a cast, which means that the
        # original cdata to which we attached the root is destroied, and thus
        # the root is freed.
        d = self._from_ht(ptr)
        if init is not None:
            d.update(init)
        return d

    def from_pointer(self, ptr):
        ht = cfuffi.cast('cfuhash_table_t*', ptr)
        return self._from_ht(ht)

    def _from_ht(self, ht):
        if self.default_factory is not None:
            return DefaultDictInstance(self, ht, self.default_factory)
        else:
            return DictInstance(self, ht)





class DictInstance(object):

    def __init__(self, dictype, ht):
        self.dictype = dictype
        self.ht = ht
        self.retbuffer = cfuffi.new('void*[1]') # passed to cfuhash_get_data

    def __repr__(self):
        addr = int(cfuffi.cast('long', self.ht))
        return '<shm dict [%s: %s] at 0x%x>' % (self.dictype.keytype,
                                                self.dictype.valuetype,
                                                addr)

    def as_cdata(self):
        return self.ht

    def _key(self, key):
        return self.dictype.keyconverter.from_python(key, ensure_shm=False, as_voidp=True)

    def __getitem__(self, ckey):
        t = self.dictype
        key = self._key(ckey)
        ret = cfuhash.get_data(self.ht, key, t.keysize,
                                   self.retbuffer, cfuffi.NULL)
        if ret == 0:
            return self.__missing__(ckey)
        value = self.retbuffer[0]
        value = t.ffi.cast(t.valuetype, value)
        return t.valueconverter.to_python(value)

    def __missing__(self, key):
        raise KeyError(key)

    def __setitem__(self, key, value):
        t = self.dictype
        key = self._key(key)
        value = t.valueconverter.from_python(value)
        value = t.ffi.cast('void*', value)
        cfuhash.put_data(self.ht, key, t.keysize, value, 0, cfuffi.NULL)

    def __contains__(self, key):
        t = self.dictype
        key = self._key(key)
        return bool(cfuhash.exists_data(self.ht, key, t.keysize))

    def __delitem__(self, key):
        t = self.dictype
        key = self._key(key)
        ret = cfuhash.delete_data(self.ht, key, t.keysize)
        if ret == t.ffi.NULL:
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def update(self, d):
        if hasattr(d, 'keys'):
            items = d.items()
        else:
            items = d
        for key, value in items:
            self[key] = value

    def keys(self):
        t = self.dictype
        sizeptr = cfuffi.new('size_t[1]')
        keys_array = cfuhash.keys(self.ht, sizeptr, True)
        if keys_array == cfuffi.NULL:
            raise MemoryError
        try:
            size = sizeptr[0]
            keys = []
            for i in range(size):
                key = keys_array[i]
                key = t.keyconverter.to_python(key, force_cast=True)
                keys.append(key)
            return keys
        finally:
            cfuhash._lib.free(keys_array)

    def values(self):
        vals = []
        for k in self.keys():
            vals.append(self[k])
        return vals

    def items(self):
        res = []
        for k in self.keys():
            res.append((k, self[k]))
        return res

    iterkeys = keys
    itervalues = values
    iteritems = items

class DefaultDictInstance(DictInstance):

    def __init__(self, dictype, ht, default_factory):
        DictInstance.__init__(self, dictype, ht)
        self.default_factory = default_factory

    def __missing__(self, key):
        value = self.default_factory()
        self[key] = value
        return value
