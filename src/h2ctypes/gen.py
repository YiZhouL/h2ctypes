import os
import re
import shutil

from .project import Solution, Header
from .template import *
from .decl import STRUCT_DECL, TYPEDEF_DECL, ENUM_DECL, FUNCTION_DECL, UNION_DECL, set_text_template, \
    is_legal_id


class CtypesDllGenerator:
    def __init__(self, solution: Solution):
        self._solution = solution

    def generate(self):
        output_dir = self._solution.get_abs_output_arch_dir()
        dependencies_path = os.path.join(output_dir, "dependencies")
        cpp_header_path = os.path.join(output_dir, "origins")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if not os.path.exists(dependencies_path):
            os.makedirs(dependencies_path)
        if not os.path.exists(cpp_header_path):
            os.makedirs(cpp_header_path)
        with open(os.path.join(dependencies_path, "__init__.py"), "w"):
            pass

        shutil.copy(os.path.join(os.path.dirname(__file__), "com.py"), dependencies_path)
        for header in self._solution.user_headers.values():
            if os.path.exists(header.path):
                shutil.copy(header.path, os.path.join(cpp_header_path, header.name + ".h"))
            if header.name != self._solution.root_header.name:
                with open(os.path.join(dependencies_path, header.py_filename), "w", encoding="utf-8") as f:
                    f.write(self._lint(self._construct(header)))
        # root header
        with open(os.path.join(output_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write(self._lint(self._construct(self._solution.root_header, is_top=True)))
        # construct builtin.py
        with open(os.path.join(dependencies_path, self._solution.builtin_header.py_filename), "w", encoding="utf-8") as f:
            f.write(self._lint(self._construct(self._solution.builtin_header)))
        # 最外层导入代码
        with open(os.path.join(self._solution.get_abs_output_dir(), "__init__.py"), "w", encoding="utf-8") as f:
            f.write("""import platform

sub_package = platform.system() + platform.architecture()[0][:2]

if sub_package == "Windows64":
    from .Windows64 import *
elif sub_package == "Windows32":
    from .Windows32 import *
elif sub_package == "Linux64":
    from .Linux64 import *
elif sub_package == "Linux32":
    from .Linux32 import *
else:
    raise ImportError""")

    def _construct(self, header: Header, is_top=False) -> str:
        decls = [item for item in header.defined_decls.values()
                 if isinstance(item, (STRUCT_DECL, TYPEDEF_DECL, ENUM_DECL, FUNCTION_DECL, UNION_DECL))
                 and is_legal_id(item.spelling)]
        headers = [h for h in self._solution.chain_headers[:self._solution.chain_headers.index(header)]]
        part0 = "From {}".format(str(header))
        if is_top:
            part1 = "".join(["from .dependencies.{} import *\n".format(h.name) for h in headers])
            part2 = "\n".join([item.generate_declaration() for item in decls if not isinstance(item, FUNCTION_DECL)])
            part3 = "\n".join([item.generate() for item in decls])
            part5 = "\n".join([item.generate_declaration() for item in decls if isinstance(item, FUNCTION_DECL)])
            part4 = "\n".join(["\t\tself.{}: {} = create_dll_interface({}, self._dll, '{}')".format(decl.spelling,
                                                                                                    decl.spelling,
                                                                                                    decl.spelling,
                                                                                                    decl.spelling)
                               for decl in header.export_interfaces if is_legal_id(decl.spelling)])
            return set_text_template(DLL_TOP_HEADER_TEMPLATE, 0, part0, part1, part2, part3, part5, "", part4)
        else:
            part1 = "".join(["from .{} import *\n".format(h.name) for h in headers])
            part2 = "\n".join([item.generate_declaration() for item in decls if not isinstance(item, FUNCTION_DECL)])
            part3 = "\n".join([item.generate() for item in decls])
            part5 = "\n".join([item.generate_declaration() for item in decls if isinstance(item, FUNCTION_DECL)])
            part4 = ", ".join(set(["\"{}\"".format(decl.spelling) for decl in decls]))
            return set_text_template(DLL_DEPENDENCY_HEADER_TEMPLATE, 0, part0, part1, part2, part3, part5, part4)

    @staticmethod
    def _lint(content):
        for old, new in [("\n+", "\n"),
                         ("\t", "    "),
                         ("const ", ""),
                         (r"POINTER\(None\)", "c_void_p"),
                         (r"POINTER\(c_char\)", "c_char_p"),
                         (r"POINTER\(c_wchar\)", "c_wchar_p"),
                         ("[a-zA-Z0-9_]+::", "")]:
            content = re.sub(old, new, content)
        return content
