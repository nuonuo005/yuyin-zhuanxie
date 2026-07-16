from __future__ import annotations

import ctypes
from ctypes import wintypes

# ── Windows API 常量 ──────────────────────────────────────────
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# ── 64 位兼容：显式设置 restype / argtypes ──────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.restype = wintypes.BOOL
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.Sleep.argtypes = [wintypes.DWORD]


def read_clipboard() -> str:
    """通过 Windows API 读取 Unicode 文字。

    剪贴板中如果是图片、文件等非文字内容，直接返回空字符串。
    """
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""

    for _ in range(10):
        if user32.OpenClipboard(0):
            break
        kernel32.Sleep(30)
    else:
        return ""

    locked = None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return ""
        return ctypes.wstring_at(locked)
    except (OSError, ValueError):
        return ""
    finally:
        if locked:
            kernel32.GlobalUnlock(handle)
        user32.CloseClipboard()


def write_clipboard(text: str) -> bool:
    """通过 Windows API 写入剪贴板，数据不依赖窗口生命周期。

    如果 Windows API 路径失败，回退到 Tkinter 兜底方案。
    """
    if not text:
        return False

    # 尝试打开剪贴板（最多重试 5 次，每次间隔 20ms）
    for _ in range(10):
        if user32.OpenClipboard(0):
            break
        kernel32.Sleep(30)
    else:
        return _write_clipboard_tk(text)

    fallback_needed = False
    h_global = None
    try:
        if not user32.EmptyClipboard():
            raise OSError("无法清空系统剪贴板")

        # UTF-16LE 编码，含结尾 \0
        encoded = (text + "\0").encode("utf-16-le")
        size = len(encoded)

        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h_global:
            raise OSError("GlobalAlloc 失败")

        locked = kernel32.GlobalLock(h_global)
        if not locked:
            raise OSError("GlobalLock 失败（返回 NULL）")

        ctypes.memmove(locked, encoded, size)
        kernel32.GlobalUnlock(h_global)

        if not user32.SetClipboardData(CF_UNICODETEXT, h_global):
            raise OSError("SetClipboardData 失败")
        # SetClipboardData 成功后，内存所有权交给 Windows。
        h_global = None
    except Exception:
        fallback_needed = True
        if h_global:
            kernel32.GlobalFree(h_global)
    finally:
        user32.CloseClipboard()

    if fallback_needed:
        return _write_clipboard_tk(text)
    return True


def _write_clipboard_tk(text: str) -> bool:
    """Tkinter 兜底写入。创建临时 root，写入后延时销毁以确保数据提交到系统剪贴板。"""
    import tkinter as tk

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.after(100, root.quit)
        root.mainloop()
        return True
    except Exception:
        return False
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
