import py

def _compile_def(src):
    d = {}
    exec src.compile() in d
    del d['__builtins__']
    assert len(d) == 1
    return d.values()[0]

class immutable_struct(object):
    """
    class decorator, to wrap a cffi struct into an immutable Python class
    """

    def __init__(self, ffi, ctype):
        self.ffi = ffi
        self.ctype = ffi.typeof(ctype)
        if self.ctype.item.kind != 'struct':
            raise TypeError("ctype must be a pointer to a struct, got %s" % self.ctype)

    def __call__(self, cls):
        cls.ffi = self.ffi
        cls.ctype = self.ctype
        self.add_ctor(cls)
        for name, field in self.ctype.item.fields:
            self.add_property(cls, name, field)
        return cls

    def add_ctor(self, cls):
        # def __init__(self, x, y):
        #     self._ptr = self.ffi.new(self.ctype)
        #     self._ptr.x = x
        #     self._ptr.y = y
        #
        fieldnames = [name for name, field in self.ctype.item.fields]
        paramlist = ', '.join(fieldnames)
        bodylines = []
        bodylines.append('self._ptr = self.ffi.new(self.ctype)')
        for fieldname in fieldnames:
            line = 'self._ptr.%s = %s' % (fieldname, fieldname)
            bodylines.append(line)
        body = py.code.Source(bodylines)
        init = body.putaround('def __init__(self, %s):' % paramlist)
        cls.__init__ = _compile_def(init)

    def add_property(self, cls, fieldname, field):
        # @property
        # def x(self):
        #     return self._ptr.x
        #
        src = py.code.Source("""
            def getter(self):
                return self._ptr.%s
        """ % fieldname)
        getter = _compile_def(src)
        getter.__name__ = fieldname
        getter = property(getter)
        setattr(cls, fieldname, getter)
