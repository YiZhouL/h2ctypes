import logging
import typing as tp

from clang.cindex import Cursor

from .project import Solution, Header
from .decl import Decl, UNEXPOSED_DECL, VAR_DECL, ENUM_DECL, PARM_DECL, UNION_DECL, STRUCT_DECL, \
    FIELD_DECL, FUNCTION_DECL, TYPEDEF_DECL, ENUM_CONSTANT_DECL


class CursorTranslator:
    protocols: tp.Dict[str, tp.Type[Decl]] = {}

    def __init__(self, solution: Solution):
        self._solution = solution

    def translate_all(self, cursors: tp.Iterable[Cursor]):
        for cursor in cursors:
            self.translate(cursor)

    def translate(
        self,
        cursor: Cursor,
        is_ignore=False,
        is_builtin=False
    ) -> tp.Optional[Decl]:
        decl, header = self._get_available_decl_and_header(cursor, is_builtin)
        if decl:
            self._solution.pre_define(decl)
            decl.translate(self._solution, is_builtin=is_builtin, is_ignore=is_ignore)
            if not is_ignore:
                self._solution.define(decl)
                header.define(decl)
            return decl

    def _get_available_decl_and_header(
        self, cursor: Cursor,
        is_builtin: bool = False
    ) -> tp.Tuple[tp.Optional[Decl], tp.Optional[Header]]:
        if cursor.location.file:
            decl_type = self.protocols.get(cursor.kind.name)
            if decl_type:
                if is_builtin:
                    header = self._solution.builtin_header
                else:
                    header = self._solution.get_header(cursor.location.file.name)

                if header:
                    return decl_type(cursor), header
            else:
                logging.warning("{}<{}> Not Found!".format(cursor.kind.name, cursor.spelling))
        return None, None

    @classmethod
    def register(cls, *decl_types):
        for decl in decl_types:
            cls.protocols[decl.__name__] = decl


CursorTranslator.register(
    UNEXPOSED_DECL,
    VAR_DECL,
    ENUM_DECL,
    PARM_DECL,
    UNION_DECL,
    STRUCT_DECL,
    FIELD_DECL,
    FUNCTION_DECL,
    TYPEDEF_DECL,
    ENUM_CONSTANT_DECL
)
