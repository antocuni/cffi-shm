import py
from shm import gclib
from shm.util import (cffi_typeof, cffi_is_struct_ptr, cffi_is_string,
                      cffi_is_char_array, compile_def, identity)

def make_struct(pyffi, ctype, immutable=True):
    if immutable:
        base = BaseImmutableStruct
    else:
        base = BaseStruct

    @StructDecorator(pyffi, ctype, immutable)
    class MyStruct(base):
        pass

    MyStruct.__name__ = ctype.item.cname
    return MyStruct


class BaseStruct(object):

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

class BaseImmutableStruct(BaseStruct):

    def __hash__(self):
        return hash(self._key())

    def __eq__(self, other):
        return self._key() == other._key()

    def _key(self):
        raise NotImplementedError


class StructDecorator(object):
    """
    class decorator, to wrap a cffi struct into Python class. The class is
    expected to be a subclass of BaseStruct
    """

    def __init__(self, pyffi, ctype, immutable=True):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.ctype = cffi_typeof(self.ffi, ctype)
        self.immutable = immutable
        if not cffi_is_struct_ptr(self.ffi, self.ctype):
            raise TypeError("ctype must be a pointer to a struct, got %s" % self.ctype)
        self.fieldnames = [name for name, field in self.ctype.item.fields]

    def __call__(self, cls):
        cls.pyffi = self.pyffi
        cls.ctype = self.ctype
        self.add_ctor(cls)
        if self.immutable:
            self.add_key(cls)
        #
        for name, field in self.ctype.item.fields:
            self.add_property(cls, name, field)
        return cls

    def add_ctor(self, cls):
        # def _init(self, x, y):
        #     self._ptr = gclib.new(self.pyffi.ffi, self.ctype)
        #     self.__set_x(x)
        #     self.__set_y(y)
        #
        # def __init__(self, x, y):
        #     self._init(x, y)
        paramlist = ', '.join(self.fieldnames)
        bodylines = []
        bodylines.append('self._ptr = gclib.new(self.pyffi.ffi, self.ctype)')
        for fieldname in self.fieldnames:
            line = 'self.__set_{x}({x})'.format(x=fieldname)
            bodylines.append(line)
        body = py.code.Source(bodylines)
        _init = body.putaround('def _init(self, %s):' % paramlist)
        cls._init = compile_def(_init, gclib=gclib)
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

    def add_property(self, cls, fieldname, field):
        getter = self.getter(cls, fieldname, field)
        setter = self.setter(cls, fieldname, field)
        if self.immutable:
            p = property(getter)
        else:
            p = property(getter, setter)
        setattr(cls, fieldname, p)

    def getter(self, cls, fieldname, field):
        conv = self.pyffi.get_converter(field.type)
        src = py.code.Source("""
            def __get_{x}(self):
                return conv.to_python(self._ptr.{x})
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn

    def setter(self, cls, fieldname, field):
        conv = self.pyffi.get_converter(field.type)
        src = py.code.Source("""
            def __set_{x}(self, value):
                self._ptr.{x} = conv.from_python(value)
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn
