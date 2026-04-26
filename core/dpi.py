import ctypes
from ctypes import wintypes


DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
PROCESS_PER_MONITOR_DPI_AWARE = 2
ERROR_ACCESS_DENIED = 5
S_OK = 0


def set_process_dpi_awareness():
    """Set the process DPI mode before any UI/window handles are created."""
    if not hasattr(ctypes, "WinDLL"):
        return False, "unsupported"

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_context = user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [wintypes.HANDLE]
        set_context.restype = wintypes.BOOL
        if set_context(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return True, "per-monitor-v2"
        error = ctypes.get_last_error()
        if error == ERROR_ACCESS_DENIED:
            return True, "already-set"
    except (AttributeError, OSError):
        pass

    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        set_awareness = shcore.SetProcessDpiAwareness
        set_awareness.argtypes = [ctypes.c_int]
        set_awareness.restype = ctypes.c_long
        result = set_awareness(PROCESS_PER_MONITOR_DPI_AWARE)
        if result == S_OK:
            return True, "per-monitor"
        if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
            return True, "already-set"
    except (AttributeError, OSError):
        pass

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_aware = user32.SetProcessDPIAware
        set_aware.restype = wintypes.BOOL
        if set_aware():
            return True, "system-aware"
        if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
            return True, "already-set"
    except (AttributeError, OSError):
        pass

    return False, "failed"


def get_window_dpi(hwnd):
    """Return the DPI for a window handle, falling back to 96 when unavailable."""
    if not hwnd or not hasattr(ctypes, "WinDLL"):
        return 96

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_dpi = user32.GetDpiForWindow
        get_dpi.argtypes = [wintypes.HWND]
        get_dpi.restype = wintypes.UINT
        dpi = int(get_dpi(wintypes.HWND(hwnd)))
        if dpi > 0:
            return dpi
    except (AttributeError, OSError):
        pass

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        get_dc = user32.GetDC
        release_dc = user32.ReleaseDC
        get_caps = gdi32.GetDeviceCaps
        get_dc.argtypes = [wintypes.HWND]
        get_dc.restype = wintypes.HDC
        release_dc.argtypes = [wintypes.HWND, wintypes.HDC]
        get_caps.argtypes = [wintypes.HDC, ctypes.c_int]
        get_caps.restype = ctypes.c_int

        dc = get_dc(wintypes.HWND(hwnd))
        if dc:
            try:
                dpi = int(get_caps(dc, 88))  # LOGPIXELSX
                if dpi > 0:
                    return dpi
            finally:
                release_dc(wintypes.HWND(hwnd), dc)
    except (AttributeError, OSError):
        pass

    return 96


def dpi_scale_for_window(hwnd):
    return max(0.5, min(get_window_dpi(hwnd) / 96.0, 4.0))
