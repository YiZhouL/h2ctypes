import logging

from clang.cindex import Type, TypeKind

from .project import Solution
from .com import DEFAULT_LACK_C_TYPE_STR, IsInCompeteArrayType, IsRefArg, IsConstArg, UNEXPOSED_TYPE_STR


def is_legal_id(id_: str) -> bool:
    if id_:
        id_ = id_.split()[-1]
    return all(map(lambda c: c in "_1234567890aqzxswedcvfrtgbnhyujmkiolpQAZXSWEDCVFRTGBNHYUJMKIOLP", id_))


class TypeTranslator:
    type2ctype = {
        # CLANG_TYPE: ()
        TypeKind.VOID: 'None',  # because ctypes.POINTER(None) == c_void_p
        TypeKind.BOOL: 'c_bool',
        TypeKind.CHAR_U: 'c_ubyte',  # ?? used for PADDING
        TypeKind.UCHAR: 'c_ubyte',  # unsigned char
        TypeKind.CHAR16: 'c_wchar',  # char16_t
        TypeKind.CHAR32: 'c_wchar',  # char32_t
        TypeKind.USHORT: 'c_ushort',
        TypeKind.UINT: 'c_uint',
        TypeKind.ULONG: 'c_ulong',
        TypeKind.ULONGLONG: 'c_ulonglong',
        TypeKind.UINT128: 'c_uint128',
        TypeKind.CHAR_S: 'c_char',  # char
        TypeKind.SCHAR: 'c_byte',  # signed char
        TypeKind.WCHAR: 'c_wchar',
        TypeKind.SHORT: 'c_short',
        TypeKind.INT: 'c_int',
        TypeKind.LONG: 'c_long',
        TypeKind.LONGLONG: 'c_longlong',
        TypeKind.INT128: 'c_int128',
        TypeKind.FLOAT: 'c_float',
        TypeKind.DOUBLE: 'c_double',
        TypeKind.LONGDOUBLE: 'c_longdouble',
        TypeKind.NULLPTR: 'c_void_p'
    }

    def __init__(self, solution: Solution):
        self._solution = solution

    def translate(self, T: Type, is_typing=False, **kwargs) -> str:
        if is_typing:
            T = T.get_canonical()
        kind = T.kind
        if kind in self.type2ctype:
            return self.type2ctype[kind]
        meth = getattr(self, kind.name, None)
        if meth:
            if T.is_const_qualified():
                return "{}({})".format("" if is_typing else IsConstArg.__name__, meth(T, is_typing, **kwargs))
            else:
                return meth(T, is_typing, **kwargs)
        else:
            logging.error("{} TypeKind Not Found!".format(kind.name))
            return DEFAULT_LACK_C_TYPE_STR

    def CONSTANTARRAY(self, T: Type, is_typing=False):
        return "({} * {})".format(self.translate(T.element_type, is_typing), T.element_count)

    def INCOMPLETEARRAY(self, T: Type, is_typing=False):
        return "{}({} * 0)".format(IsInCompeteArrayType.__name__, self.translate(T.element_type, is_typing))

    def POINTER(self, T: Type, is_typing=False):
        pointer = T.get_pointee()
        if pointer.kind == TypeKind.FUNCTIONPROTO:
            return self.translate(pointer, is_typing)
        else:
            return "POINTER({})".format(self.translate(pointer, is_typing))

    def UNEXPOSED(self, T: Type, is_typing=False):
        return UNEXPOSED_TYPE_STR

    def ELABORATED(self, T: Type, is_typing=False):
        return self.translate(T.get_canonical(), is_typing=is_typing)

    def TYPEDEF(self, T: Type, is_typing=False):
        decl = T.get_declaration()
        if not self._solution.is_defined(decl):
            return self.translate(decl.type.get_canonical(), is_typing)
        else:
            return decl.spelling

    def RECORD(self, T: Type, is_typing=False):
        if not self._solution.is_defined(T.get_declaration().hash) and not self._solution.is_defined(T.spelling):
            if is_legal_id(T.spelling) \
                    and self._solution.cursor_handler.translate(T.get_declaration(), is_builtin=True):
                return T.spelling
            else:
                return DEFAULT_LACK_C_TYPE_STR
        return T.spelling

    def ENUM(self, T: Type, is_typing=False):
        return self.translate(T.get_declaration().enum_type, is_typing)

    def LVALUEREFERENCE(self, T: Type, is_typing=False):
        return "{}(POINTER({}))".format(IsRefArg.__name__, self.translate(T.get_pointee(), is_typing))

    def FUNCTIONPROTO(self, T: Type, is_typing=False):
        return "CFUNCTYPE({}, {})".format(self.translate(T.get_result(), is_typing),
                                          ", ".join([self.translate(arg, is_typing) for arg in T.argument_types()]))
