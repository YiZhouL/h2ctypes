import copy
import logging
import os
import typing as tp

from clang.cindex import Config, TranslationUnit, Index, Diagnostic

from .project import get_human_abs_filename, Header, HeaderType, Solution
from .type import TypeTranslator
from .cursor import CursorTranslator
from .gen import CtypesDllGenerator


class WorkSpace:
    BUILTIN_FILENAME = "builtin.h"

    clang_options = TranslationUnit.PARSE_SKIP_FUNCTION_BODIES \
                    | TranslationUnit.PARSE_PRECOMPILED_PREAMBLE \
                    | TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION
    clang_args = ["-x", "c++"]

    def __init__(self, libclang_path: str, debug=False, root_path: str = ""):
        """
        :param root_path: 设置一个工作根目录，后续所有需要翻译的用户头文件从该目录过滤
        :param libclang_path: libclang目录
        :param debug: True 调试模式
        """
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        if not os.path.isabs(root_path):
            root_path = os.path.join(os.getcwd(), root_path)
        self.path = get_human_abs_filename(root_path)
        Config.set_library_path(libclang_path)
        self.index = Index.create()

    def translate(
            self,
            header_file_path: str,
            *,
            is_m32=False,
            user_macros: tp.Iterable[tp.Union[str, tp.Tuple[tp.Any, tp.Any]]] = None,
            include_files: tp.Iterable[str] = None,
            include_search_paths: tp.Iterable[str] = None,
            output_dir="out",
            include_user_files: tp.Iterable[str] = None
    ):
        """
        翻译一个头文件
        :param header_file_path: 需要翻译的头文件路径
        :param is_m32: 是否作为32位翻译
        :param user_macros: 用户添加的宏
        :param include_files: 用户指定的头文件
        :param include_search_paths: 用户指定的头文件搜索路径
        :param output_dir: 输出目录
        :param include_user_files: 额外用户头文件
        :return:
        """
        args = copy.deepcopy(self.clang_args)
        # gen clang args
        args.append("-m32" if is_m32 else "-m64")
        if user_macros:
            for item in user_macros:
                if isinstance(item, str):
                    args.append("-D {}=1".format(item))
                else:
                    args.append("-D {}={}".format(item[0], item[1]))
        if include_files:
            args.extend(["-include{}".format(include) for include in include_files])
        if include_search_paths:
            args.extend(["-I{}".format(path) for path in include_search_paths])

        logging.debug("clang args: {}".format(args))

        if not os.path.isabs(header_file_path):
            header_file_path = os.path.join(os.getcwd(), header_file_path)

        solution = self._parse_include_header(header_file_path, args, include_user_files)
        type_handler = TypeTranslator(solution)
        cursor_handler = CursorTranslator(solution)
        solution.type_handler = type_handler
        solution.cursor_handler = cursor_handler
        solution.output_dir = output_dir
        solution.is_m32 = is_m32

        # translate all cursor
        cursor_handler.translate_all(solution.root_tu.cursor.get_children())

        # gen processing
        generator = CtypesDllGenerator(solution)
        generator.generate()

    def _parse_include_header(self, header_file_path, args, include_user_files=None) -> Solution:
        if include_user_files is None:
            include_user_files = set()
        else:
            include_user_files = set(get_human_abs_filename(file) or file for file in include_user_files)

        root_tu = self.index.parse(header_file_path, args=args, options=self.clang_options)
        warnings = [w for w in root_tu.diagnostics if w.severity == Diagnostic.Warning]
        errors = [w for w in root_tu.diagnostics if w.severity == Diagnostic.Error]
        fatals = [w for w in root_tu.diagnostics if w.severity == Diagnostic.Fatal]
        if warnings:
            [logging.warning(warning) for warning in warnings]
        if errors:
            [logging.error(err) for err in errors]
        if fatals:
            [logging.critical(fatal) for fatal in fatals]
        built_header = Header(os.path.join(self.path, self.BUILTIN_FILENAME), HeaderType.VIRTUAL)  # include a virtual header
        _user_headers = {}
        _chain_headers = []

        def _get_header(name: str, type_=HeaderType.REAL) -> Header:
            name = get_human_abs_filename(name)
            if name not in _user_headers:
                h = Header(name, type_)
                _user_headers[name] = h
            else:
                h = _user_headers[name]
            return h

        def _parse_tu(tu: TranslationUnit):
            for file in tu.get_includes():
                if file.source is None:  # -include
                    _chain_headers.append(_get_header(file.include.name, HeaderType.CLANG_INCLUDE))
                    continue

                source_name = get_human_abs_filename(file.source.name)
                include_name = get_human_abs_filename(file.include.name)
                if (self._is_user_include_file(source_name, include_user_files) or
                        (source_name.startswith(self.path) and include_name.startswith(self.path))):
                    source_header = _get_header(source_name)
                    include_header = _get_header(include_name)

                    if source_name not in _chain_headers:
                        _chain_headers.append(source_header)
                    if include_header not in _chain_headers:
                        index = _chain_headers.index(source_header)
                        _chain_headers.insert(index, include_header)

        _parse_tu(root_tu)
        _chain_headers.insert(0, built_header)
        # make sure root_header exists
        root_header = _get_header(header_file_path)
        if root_header in _chain_headers:
            _chain_headers.remove(root_header)
        _chain_headers.append(root_header)

        return Solution(
            root_tu=root_tu,
            root_header=root_header,
            builtin_header=built_header,
            user_headers=_user_headers,
            chain_headers=_chain_headers
        )

    @staticmethod
    def _is_user_include_file(file: str, files: tp.Iterable[str]) -> bool:
        for name in files:
            if file.endswith(name):
                return True
        return False
