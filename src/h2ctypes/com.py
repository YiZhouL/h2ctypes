from ctypes import *
from functools import partial

# type缺失时，默认的c-type，一般是平台内建类型，这部分需要手动确认
DEFAULT_LACK_C_TYPE = c_ulonglong
DEFAULT_LACK_C_TYPE_STR = "DEFAULT_LACK_C_TYPE"
UNEXPOSED_TYPE = c_ulonglong
UNEXPOSED_TYPE_STR = "UNEXPOSED_TYPE"


def IsConstArg(obj):
    """标识一个const参数"""
    return obj


def IsCallableArg(obj):
    """标识一个回调参数"""
    return obj


def IsInCompeteArrayType(obj):
    """标识一个不完整数组类型"""
    return obj


def IsRefArg(obj):
    """引用参数"""
    return obj


def IsEnumField(obj):
    def inner(type_):
        return type_
    return inner


class IsEnumType:
    """表示一个枚举类型"""
    pass


def create_dll_interface(f: CFUNCTYPE, dll, name):
    """根据函数指针定义dll中某个接口"""
    if hasattr(dll, name):
        obj = getattr(dll, name)
        obj.argtypes = getattr(f, "_argtypes_")
        obj.restype = getattr(f, "_restype_")
        return obj


class CtypesDll:
    """ctypes dll"""
    def __init__(self, dll_file_path: str):
        self._dll = CDLL(dll_file_path)
        self._setup()

    def _setup(self):
        ...

    @property
    def origin_dll(self) -> CDLL:
        return self._dll
