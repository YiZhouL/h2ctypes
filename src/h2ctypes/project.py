from dataclasses import dataclass, field
import os
import platform
import typing as tp
from functools import lru_cache

from clang.cindex import TranslationUnit, Cursor, LinkageKind

Decl = tp.ForwardRef("Decl")


@lru_cache
def get_human_abs_filename(filename: str) -> tp.Optional[str]:
    """
    :param filename: 绝对路径
    :return: 人眼友好路径
    """
    filename = filename.replace("\\", "/")
    if not os.path.isabs(filename):
        return

    names = filename.split("/")
    paths = []
    for index, item in enumerate(names):
        if item == "..":
            paths.pop(-1)
        elif item != ".":
            paths.append(item)

    return "/".join(paths)


class HeaderType:
    REAL = 1
    VIRTUAL = 2
    CLANG_INCLUDE = 3


class Header:
    def __init__(self, path: str, type_=HeaderType.REAL):
        self.path = get_human_abs_filename(path)
        self.type = type_
        self.include_headers = {}
        self.defined_decls: tp.Dict[Hash, Decl] = {}

    @property
    def dirname(self) -> str:
        return os.path.dirname(self.path)

    def include(self, h: "Header"):
        self.include_headers[h.path] = h

    @property
    def name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0].replace("-", "_")

    @property
    def py_filename(self) -> str:
        return self.name + ".py"

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def define(self, decl: Decl):
        self.defined_decls[decl.hash] = decl

    @property
    def export_interfaces(self):
        from .decl import FUNCTION_DECL
        return [decl for decl in self.defined_decls.values()
                if isinstance(decl, FUNCTION_DECL) and decl.link_kind == LinkageKind.EXTERNAL]

    def __str__(self):
        return "<Header> - {}".format(self.path)


Hash = int


@dataclass
class Solution:
    root_tu: TranslationUnit
    root_header: Header
    builtin_header: Header
    user_headers: tp.Dict[str, Header] = field(default_factory=lambda: {})
    defined_decls: tp.Dict[Hash, Decl] = field(default_factory=lambda: {})
    pre_defined_namespace: tp.Set[str] = field(default_factory=lambda: set())
    pre_defined_decls: tp.Dict[Hash, Decl] = field(default_factory=lambda: {})
    type_handler: tp.Any = None
    cursor_handler: tp.Any = None
    output_dir: str = "out"
    is_m32: bool = False
    chain_headers: tp.List[Header] = field(default_factory=lambda: [])

    def define(self, decl: Decl):
        self.defined_decls[decl.hash] = decl

    def pre_define(self, decl: Decl):
        self.pre_defined_decls[decl.hash] = decl
        self.pre_defined_namespace.add(decl.spelling)

    def is_defined(self, obj: tp.Union[Cursor, Hash, str]) -> bool:
        if isinstance(obj, Hash):
            return obj in self.pre_defined_decls
        elif isinstance(obj, str):
            return obj in self.pre_defined_namespace
        return False

    def get_header(self, path: str) -> tp.Optional[Header]:
        return self.user_headers.get(get_human_abs_filename(path))

    def get_define(self, cursor: Cursor) -> tp.Optional[Decl]:
        return self.defined_decls.get(cursor.hash)

    def get_abs_output_arch_dir(self) -> str:
        if not os.path.isabs(self.output_dir):
            return os.path.join(os.getcwd(), self.output_dir, "{}{}".format(platform.system(), "32" if self.is_m32
            else "64"))
        return os.path.join(self.output_dir, "{}{}".format(platform.system(), "32" if self.is_m32
            else "64"))

    def get_abs_output_dir(self) -> str:
        if not os.path.isabs(self.output_dir):
            return os.path.join(os.getcwd(), self.output_dir)
        return self.output_dir
