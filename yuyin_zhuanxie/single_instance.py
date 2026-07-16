from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = r"Local\YuyinZhuanxieSingleton"
_MUTEX_HANDLE = None


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def acquire_single_instance() -> bool:
    global _MUTEX_HANDLE
    if os.getenv("YUYIN_ALLOW_MULTIPLE") == "1":
        return True
    if _MUTEX_HANDLE:
        return True

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _MUTEX_HANDLE = handle
    return True


def release_single_instance() -> None:
    global _MUTEX_HANDLE
    if _MUTEX_HANDLE:
        kernel32.CloseHandle(_MUTEX_HANDLE)
        _MUTEX_HANDLE = None
