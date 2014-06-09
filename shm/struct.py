import py
from shm.sharedmem import sharedmem
from shm.util import (cffi_typeof, cffi_is_struct_ptr, cffi_is_string,
                      cffi_is_char_array, compile_def, identity, ctype_pointer_to)

def make_struct(pyffi, ctype, immutable=True, converters=None):
    struct_ctype = ctype
    ptr_ctype = ctype_pointer_to(pyffi.ffi, ctype)
    decorate = StructDecorator(pyffi, ptr_ctype, immutable, converters)
    class MyStruct(BaseStruct):
        __slots__ = ()
        class __metaclass__(type):
            def __init__(cls, name, bases, dic):
                cls = decorate(cls)
                pyffi.register(struct_ctype, cls)
                pyffi.register(ptr_ctype, cls)

    MyStruct.__name__ = struct_ctype.cname
    return MyStruct


class BaseStruct(object):
    __slots__ = ('_ptr',)

    @classmethod
    def from_pointer(cls, ptr):
        ffi = cls.pyffi.ffi
        if cls.ctype != ffi.typeof(ptr):
            raise TypeError("Expected %s, got %s" % (cls.ctype, ffi.typeof(ptr)))
        self = cls.__new__(cls)
        self._ptr = ptr
        return self

    def as_cdata(self):
        return self._ptr


class StructDecorator(object):
    """
    class decorator, to wrap a cffi struct into Python class. The class is
    expected to be a subclass of BaseStruct
    """

    def __init__(self, pyffi, ctype, immutable=True, converters=None):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.ctype = cffi_typeof(self.ffi, ctype)
        self.immutable = immutable
        if not cffi_is_struct_ptr(self.ffi, self.ctype):
            raise TypeError("ctype must be a pointer to a struct, got %s" % self.ctype)
        self.fieldnames = [name for name, field in self.ctype.item.fields]
        self.converters = converters or {}

    def __call__(self, cls):
        cls.pyffi = self.pyffi
        cls.ctype = self.ctype
        cls.__immutable__ = self.immutable
        self.add_ctor(cls)
        if self.immutable:
            self.add_key(cls)
            cls.__fieldspec__ = self.make_fieldspec(cls)
        #
        for name, field in self.ctype.item.fields:
            self.add_property(cls, name, field)
        return cls

    def add_ctor(self, cls):
        # def _init(self, x, y):
        #     self._ptr = sharedmem.new(self.pyffi.ffi, self.ctype)
        #     self.__set_x(x)
        #     self.__set_y(y)
        #
        # def __init__(self, x, y):
        #     self._init(x, y)
        paramlist = ', '.join(self.fieldnames)
        bodylines = []
        bodylines.append('self._ptr = sharedmem.new(self.pyffi.ffi, self.ctype)')
        for fieldname in self.fieldnames:
            line = 'self.__set_{x}({x})'.format(x=fieldname)
            bodylines.append(line)
        body = py.code.Source(bodylines)
        _init = body.putaround('def _init(self, %s):' % paramlist)
        cls._init = compile_def(_init, sharedmem=sharedmem)
        #
        # we add the proper __init__ only if it's not already defined
        if '__init__' in cls.__dict__:
            return
        ctor = py.code.Source("""
            def __init__(self, {paramlist}):
                self._init({paramlist})
        """.format(paramlist=paramlist))
        cls.__init__ = compile_def(ctor)

    def add_key(self, cls):
        # def _key(self):
        #     return self.x, self.y
        #
        itemlist = ['self.%s' % x for x in self.fieldnames]
        items = ', '.join(itemlist)
        src = py.code.Source("""
            def _key(self):
                return %s
        """ % items)
        cls._key = compile_def(src)

        def __hash__(self):
            return hash(self._key())
        def __eq__(self, other):
            return self._key() == other._key()
        cls.__hash__ = __hash__
        cls.__eq__ = __eq__

    def make_fieldspec(self, cls):
        from shm.dict import dictffi, lib
        n = len(self.ctype.item.fields) + 1
        fieldspec = sharedmem.new_array(dictffi, 'cfuhash_fieldspec_t', n)
        for i, (fieldname, field) in enumerate(self.ctype.item.fields):
            f = fieldspec[i]
            f.name = sharedmem.new_string('%s.%s' % (self.ctype.item.cname, fieldname))
            f.offset = field.offset
            if field.type.kind in ('primitive', 'array'):
                f.kind = lib.cfuhash_primitive
                f.size = self.ffi.sizeof(field.type)
            elif cffi_is_string(self.ffi, field.type):
                f.kind = lib.cfuhash_string
                f.size = 0
            elif cffi_is_struct_ptr(self.ffi, field.type):
                pytype = self.pyffi.pytypeof(field.type)
                if not pytype.__immutable__:
                    return None
                f.kind = lib.cfuhash_pointer
                f.fieldspec = pytype.__fieldspec__
            else:
                assert False, 'unknown field kind'
        #
        fieldspec[i+1].kind = lib.cfuhash_fieldspec_stop
        return fieldspec

    def add_property(self, cls, fieldname, field):
        getter = self.getter(cls, fieldname, field)
        setter = self.setter(cls, fieldname, field)
        if self.immutable:
            p = property(getter)
        else:
            p = property(getter, setter)
        setattr(cls, fieldname, p)

    def get_converter(self, fieldname, field):
        conv = self.converters.get(fieldname)
        if conv is not None:
            return conv(self.pyffi, field.type)
        return self.pyffi.get_converter(field.type)

    def getter(self, cls, fieldname, field):
        conv = self.get_converter(fieldname, field)
        src = py.code.Source("""
            def __get_{x}(self):
                return conv.to_python(self._ptr.{x})
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn

    def setter(self, cls, fieldname, field):
        conv = self.get_converter(fieldname, field)
        src = py.code.Source("""
            def __set_{x}(self, value):
                self._ptr.{x} = conv.from_python(value)
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn

