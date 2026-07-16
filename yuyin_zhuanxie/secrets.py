from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes


DPAPI_PREFIX = "dpapi:"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


crypt32 = ctypes.windll.crypt32
kernel32 = ctypes.windll.kernel32

crypt32.CryptProtectData.restype = wintypes.BOOL
crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPCWSTR,
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
crypt32.CryptUnprotectData.restype = wintypes.BOOL
crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
kernel32.LocalFree.restype = wintypes.HLOCAL
kernel32.LocalFree.argtypes = [wintypes.HLOCAL]


def _blob_from_bytes(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(
        cbData=len(data),
        pbData=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def protect_secret(value: str) -> str:
    if not value or value.startswith(DPAPI_PREFIX):
        return value

    raw = value.encode("utf-8")
    input_blob, input_buffer = _blob_from_bytes(raw)
    output_blob = DATA_BLOB()
    _ = input_buffer

    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "语言转写 API Key",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise OSError("Windows 无法加密 API Key。")

    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, wintypes.HLOCAL))


def unprotect_secret(value: str) -> str:
    if not value or not value.startswith(DPAPI_PREFIX):
        return value

    try:
        encrypted = base64.b64decode(value[len(DPAPI_PREFIX) :], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("加密的 API Key 格式已损坏。") from exc

    input_blob, input_buffer = _blob_from_bytes(encrypted)
    output_blob = DATA_BLOB()
    description = wintypes.LPWSTR()
    _ = input_buffer

    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise OSError("API Key 无法解密，可能来自另一台电脑或另一个 Windows 用户。")

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        if description:
            kernel32.LocalFree(ctypes.cast(description, wintypes.HLOCAL))
        if output_blob.pbData:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, wintypes.HLOCAL))
