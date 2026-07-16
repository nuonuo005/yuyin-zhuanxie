from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time

# ── Win32 DLL 句柄 ────────────────────────────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── 常量 ───────────────────────────────────────────────────────
VK_CONTROL = 0x11
VK_V = 0x56
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SW_RESTORE = 9
INPUT_KEYBOARD = 1
WM_PASTE = 0x0302

# ── 64 位兼容：显式设置 restype / argtypes ──────────────────────
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [wintypes.LPVOID]

user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.AllowSetForegroundWindow.restype = wintypes.BOOL
user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, wintypes.LPDWORD]
LRESULT = ctypes.c_longlong  # 64-bit LONG_PTR
user32.SendMessageW.restype = LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetFocus.restype = wintypes.HWND
user32.SetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

# ── SendInput 64 位结构体定义 ─────────────────────────────────
ULONG_PTR = ctypes.c_ulonglong

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]

user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

# ── 验证 64 位结构体大小 ───────────────────────────────────────
_EXPECTED = 40  # 4 (type) + 4 (padding) + 32 (union = max of 24/32/8)
_ACTUAL = ctypes.sizeof(INPUT)
if _ACTUAL != _EXPECTED:
    import warnings
    warnings.warn(
        f"SendInput INPUT struct size mismatch: expected {_EXPECTED}, got {_ACTUAL}. "
        f"SendInput may fail on this platform.",
        RuntimeWarning,
    )


# ═══════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════

def get_foreground_window() -> int:
    return int(user32.GetForegroundWindow())


def get_window_process_id(hwnd: int) -> int:
    if not hwnd:
        return 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def is_own_window(hwnd: int, process_id: int | None = None) -> bool:
    if process_id is None:
        process_id = os.getpid()
    return bool(hwnd) and get_window_process_id(hwnd) == process_id


def get_cursor_position() -> tuple[int, int]:
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def set_cursor_position(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)


def click_current_mouse_position() -> None:
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


def set_foreground_window(hwnd: int) -> bool:
    """可靠地将目标窗口激活到前台（AttachThreadInput + AllowSetForegroundWindow）。"""
    if not hwnd:
        return False

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    fg_hwnd = int(user32.GetForegroundWindow())
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    attached = False
    if fg_thread and target_thread and fg_thread != target_thread:
        attached = user32.AttachThreadInput(target_thread, fg_thread, True)

    try:
        user32.AllowSetForegroundWindow(wintypes.DWORD(-1).value)
        success = user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(target_thread, fg_thread, False)

    if not success:
        # 回退：模拟 Alt 键
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        success = user32.SetForegroundWindow(hwnd)

    return bool(success)


# ═══════════════════════════════════════════════════════════════
#  粘贴引擎（SendInput 主路径 + WM_PASTE 兜底）
# ═══════════════════════════════════════════════════════════════

def _send_ctrl_v_via_sendinput() -> bool:
    """使用 SendInput 发送 Ctrl+V（输入队列级别，浏览器/Electron 兼容）。

    相比 keybd_event：SendInput 注入到硬件输入队列，被视为「真实按键」，
    现代浏览器（Chrome/Edge/Electron）能够正常处理。
    """
    inputs = (INPUT * 4)()

    # Ctrl down — 同时发送 VK 和 scancode 以确保兼容性
    inputs[0].type = INPUT_KEYBOARD
    inputs[0].ki.wVk = VK_CONTROL
    inputs[0].ki.wScan = 0x1D  # left Ctrl scancode

    # V down
    inputs[1].type = INPUT_KEYBOARD
    inputs[1].ki.wVk = VK_V
    inputs[1].ki.wScan = 0x2F  # V key scancode

    # V up
    inputs[2].type = INPUT_KEYBOARD
    inputs[2].ki.wVk = VK_V
    inputs[2].ki.wScan = 0x2F
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP

    # Ctrl up
    inputs[3].type = INPUT_KEYBOARD
    inputs[3].ki.wVk = VK_CONTROL
    inputs[3].ki.wScan = 0x1D
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP

    sent = user32.SendInput(4, inputs, ctypes.sizeof(INPUT))
    return sent == 4


def _send_wm_paste(hwnd: int) -> bool:
    """通过 WM_PASTE 消息直接向目标窗口粘贴（不依赖键盘焦点）。

    适用于 SendInput 被 UIPI 阻止的场景（如高权限浏览器标签页）。
    WM_PASTE 发送到顶层窗口后，Windows 会将其路由到焦点控件。
    """
    if not hwnd:
        return False
    result = user32.SendMessageW(hwnd, WM_PASTE, 0, 0)
    return result == 0  # WM_PASTE 返回 0 表示成功


def paste_to_window(hwnd: int) -> bool:
    """将剪贴板内容粘贴到目标窗口的光标位置。

    策略（按优先级）：
    1. 激活目标窗口 → SendInput Ctrl+V（主路径，支持所有现代应用）
    2. 如果 SendInput 失败 → WM_PASTE 消息（兜底，不依赖焦点）
    3. 如果窗口激活失败 → 直接用 WM_PASTE（仍可能成功）
    """
    if not hwnd:
        return False

    # 尝试激活窗口
    focused = set_foreground_window(hwnd)
    if focused:
        # 给浏览器足够时间完成焦点切换（Chrome/Edge 需要 >100ms）
        time.sleep(0.15)
        if _send_ctrl_v_via_sendinput():
            return True

    # 兜底：WM_PASTE 不依赖焦点，直接向窗口发消息
    return _send_wm_paste(hwnd)
