import typing as tp

from clang.cindex import Cursor, CursorKind

from .project import Solution
from .com import IsEnumField, IsCallableArg
from .type import is_legal_id
from .template import *

anonymous_count = 0


def get_anonymous_name(type_: str = None) -> str:
    global anonymous_count
    anonymous_count += 1
    return "Anonymous{}{}".format(anonymous_count, "_" + type_ if type_ else "")


def set_text_template(template: str, depth, *args):
    strings = template.format(*args).split("\n")
    for index, string in enumerate(strings[:-1]):
        strings[index] = "\t" * depth + string
    return "\n".join(strings)


class Decl:
    spelling: str
    hash: int
    cursor: Cursor
    type: str
    typing: str
    value: tp.Any
    items: tp.List["Decl"]
    comment: str

    def __init__(self, cursor: Cursor):
        self.spelling = cursor.spelling
        self.hash = cursor.hash
        self.cursor = cursor
        self.link_kind = cursor.linkage
        self.items = []

        if not self.spelling:
            self.spelling = get_anonymous_name()

    def translate(self, solution: Solution, **kwargs): ...

    def generate(self, depth=0) -> str: ...

    def generate_declaration(self, depth=0) -> str: ...


class UNEXPOSED_DECL(Decl):
    def generate(self, depth=0) -> str:
        return ""

    def generate_declaration(self, depth=0) -> str:
        return ""

    def translate(self, solution: Solution, **kwargs):
        for child in self.cursor.get_children():
            solution.cursor_handler.translate(child)


class ENUM_DECL(Decl):
    def generate(self, depth=0) -> str:
        return ""

    def generate_declaration(self, depth=0) -> str:
        return set_text_template(ENUM_DEFINE_TEMPLATE, depth, self.spelling, "".join([item.generate(depth + 1)
                                                                                      for item in self.items]))

    def translate(self, solution: Solution, **kwargs):
        self.type = solution.type_handler.translate(self.cursor.enum_type)

        for field in self.cursor.get_children():
            self.items.append(solution.cursor_handler.translate(field, is_ignore=True))


class ENUM_CONSTANT_DECL(Decl):
    def generate(self, depth=0) -> str:
        return set_text_template("{} = {}\n", depth, self.spelling, self.value)

    def translate(self, solution: Solution, **kwargs):
        self.value = self.cursor.enum_value


class UNION_DECL(Decl):
    def generate(self, depth=0) -> str:
        return set_text_template(UNION_DEFINE_TEMPLATE, depth, self.spelling,
                                 "".join([item.generate(depth + 2) for item in self.items]))

    def generate_declaration(self, depth=0) -> str:
        return set_text_template(UNION_DEFEINE_DECLARATION_TEMPLATE, depth, self.spelling)

    def translate(self, solution: Solution, **kwargs):
        for field in self.cursor.get_children():
            sub_field = solution.cursor_handler.translate(
                field,
                is_ignore=(field.kind == CursorKind.FIELD_DECL),
                is_builtin=kwargs.get("is_builtin")
            )
            if field.kind == CursorKind.FIELD_DECL:
                self.items.append(sub_field)


class VAR_DECL(Decl):
    def generate(self, depth=0) -> str:
        return ""

    def generate_declaration(self, depth=0) -> str:
        return ""

    def translate(self, solution: Solution, **kwargs):
        self.type = solution.type_handler.translate(self.cursor.type)


class FIELD_DECL(Decl):
    def generate(self, depth=0) -> str:
        if self.cursor.is_bitfield():
            return set_text_template("(\"{}\", {}, {}),\n", depth, self.spelling, self.type,
                                     self.cursor.get_bitfield_width())
        else:
            return set_text_template("(\"{}\", {}),\n", depth, self.spelling, self.type)

    def generate_declaration(self, depth=0) -> str:
        return ""

    def translate(self, solution: Solution, **kwargs):
        origin = self.cursor.type
        decl = origin.get_canonical().get_declaration()
        define = solution.get_define(decl)
        if define:
            if decl.kind != CursorKind.ENUM_DECL:
                self.type = define.spelling
            else:
                self.type = "{}({})({})".format(IsEnumField.__name__, define.spelling, define.type)
        else:
            self.type = solution.type_handler.translate(origin)

        if self.type.startswith("_"):
            self.type = solution.type_handler.translate(origin)


class PARM_DECL(Decl):
    def generate(self, depth=0) -> str:
        return self.type

    def generate_declaration(self, depth=0) -> str:
        return ""

    def translate(self, solution: Solution, **kwargs):
        self.type = solution.type_handler.translate(self.cursor.type)
        self.typing = solution.type_handler.translate(self.cursor.type, is_typing=True)
        if self.is_callback:  # parm func pointer
            decl = TYPEDEF_DECL(self.cursor)
            decl.spelling = self.cursor.type.spelling or get_anonymous_name()
            decl.type = self.typing
            solution.define(decl)
            header = solution.get_header(self.cursor.location.file.name)
            if header:
                header.define(decl)
            self.type = "{}({})".format(IsCallableArg.__name__, decl.spelling)

    @property
    def is_callback(self) -> bool:
        return "CFUNCTYPE" in self.typing


class FUNCTION_DECL(Decl):
    return_type: str

    def generate(self, depth=0) -> str:
        return ""

    def generate_declaration(self, depth=0) -> str:
        return set_text_template("{} = {}\n", depth, self.spelling, self.type)

    def translate(self, solution: Solution, **kwargs):
        self.return_type = solution.type_handler.translate(self.cursor.result_type)
        for arg in self.cursor.get_children():
            if arg.kind == CursorKind.PARM_DECL:
                self.items.append(solution.cursor_handler.translate(arg, is_ignore=True))
        self.type = "CFUNCTYPE({}, {})\n".format(self.return_type, ", ".join([item.type for item in self.items]))


class TYPEDEF_DECL(Decl):
    def generate(self, depth=0) -> str:
        return ""

    def generate_declaration(self, depth=0) -> str:
        if hasattr(self, "type"):
            return set_text_template("{} = {}\n", depth, self.spelling, self.type) if self.spelling != self.type else ""
        else:
            return ""  # when same name define

    def translate(self, solution: Solution, **kwargs):
        origin = self.cursor.type
        decl = origin.get_canonical().get_declaration()
        define = solution.get_define(decl)
        if define:
            if isinstance(define, ENUM_DECL) and self.spelling != define.spelling:
                self.type = define.type
            elif self.spelling != define.spelling:
                self.type = define.spelling
        else:
            self.type = solution.type_handler.translate(origin)


class STRUCT_DECL(Decl):
    _overload_count = 0
    _pack = 1

    def generate(self, depth=0) -> str:
        if self.empty:
            return ""
        return set_text_template(C_STRUCTURE_TEMPLATE, depth, self.spelling,
                                 "".join([item.generate(depth + 1) for item in self.items]))

    def generate_declaration(self, depth=0) -> str:
        return set_text_template(C_STRUCTURE_DECLARATION_TEMPLATE, depth, self.spelling, self._pack)

    def translate(self, solution: Solution, **kwargs):

        self._pack = self.cursor.type.get_align()
        available_kind = (CursorKind.FIELD_DECL, )
        for field in self.cursor.get_children():
            if is_legal_id(field.spelling):
                sub_field = solution.cursor_handler.translate(
                    field,
                    is_ignore=field.kind in available_kind,
                    is_builtin=kwargs.get("is_builtin")
                )
                if field.kind in available_kind:
                    self.items.append(sub_field)

    @property
    def empty(self) -> bool:
        return len(self.items) == 0
