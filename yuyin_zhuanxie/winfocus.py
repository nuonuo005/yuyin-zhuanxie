from __future__ import annotations

import ctypes
import os
import time


user32 = ctypes.windll.user32
ASFW_ANY = -1
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def get_foreground_window() -> int:
    return int(user32.GetForegroundWindow())


def get_window_process_id(hwnd: int) -> int:
    if not hwnd:
        return 0
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def is_own_window(hwnd: int, process_id: int | None = None) -> bool:
    if process_id is None:
        process_id = os.getpid()
    return bool(hwnd) and get_window_process_id(hwnd) == process_id


def set_foreground_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:
        pass
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.ShowWindow(hwnd, 5)
    time.sleep(0.08)
    return bool(user32.SetForegroundWindow(hwnd))


def get_cursor_position() -> tuple[int, int]:
    point = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return (int(point.x), int(point.y))


def set_cursor_position(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)
    time.sleep(0.02)


def click_current_mouse_position() -> None:
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def paste_to_window(hwnd: int) -> bool:
    """
    聚焦目标窗口后直接 Ctrl+V。
    - 未选中文字 → 在光标位置插入
    - 已选中文字 → 替换选中内容
    不做 Ctrl+End，不强制跳到文档末尾。
    """
    if hwnd:
        set_foreground_window(hwnd)
    time.sleep(0.15)
    try:
        import keyboard
        keyboard.send("ctrl+v")
        return True
    except Exception:
        return False
