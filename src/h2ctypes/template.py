ENUM_DEFINE_TEMPLATE = """class {}(IsEnumType):
{}
"""

UNION_DEFEINE_DECLARATION_TEMPLATE = """class {}(Union): pass
"""
UNION_DEFINE_TEMPLATE = """
{}._fields_ = [
{}
]
"""
C_STRUCTURE_DECLARATION_TEMPLATE = """class {}(Structure):
    _pack_ = {}
"""
C_STRUCTURE_TEMPLATE = """
{}._fields_ = [
{}
]
"""

DLL_DEPENDENCY_HEADER_TEMPLATE = """from .com import *
# location 
# {}

# dependencies
{}
# declaration
{}
# defines
{}
# function
{}
# namespace
__all__ = [{}]
"""

DLL_TOP_HEADER_TEMPLATE = """from .dependencies.com import *
# location 
# {}

# dependencies
{}
# declaration
{}
# defines
{}
# function
{}
class {}Dll(CtypesDll):
    def _setup(self):
        super()._setup()
        # export interface
{}
"""
