import ctypes
import time
import keyboard
import pydirectinput  # 引入更成熟的底层模拟库

class Controller:
    """键盘控制器，使用 pydirectinput 解决 3D 游戏屏蔽按键问题"""
    
    def __init__(self):
        self.pressed_keys = set()
        # pydirectinput 默认会有 0.01 秒的延迟，这是为了防屏蔽设计的
        pydirectinput.PAUSE = 0.01

    def key_down(self, key_char):
        """按下按键"""
        key_char = key_char.lower()
        try:
            pydirectinput.keyDown(key_char)
            self.pressed_keys.add(key_char)
        except Exception:
            pass

    def key_up(self, key_char):
        """释放按键"""
        key_char = key_char.lower()
        try:
            pydirectinput.keyUp(key_char)
            if key_char in self.pressed_keys:
                self.pressed_keys.remove(key_char)
        except Exception:
            pass

    def key_tap(self, key_char, duration=0.15):
        """
        短按某键。
        注意：对于《异环》这种基于虚幻引擎的游戏，点按时间必须足够长 (建议 0.15 秒以上)
        否则会被游戏底层的按键防抖逻辑过滤掉。
        """
        key_char = key_char.lower()
        try:
            # 记录详细日志由上层完成，这里只做纯净的底层调用
            pydirectinput.keyDown(key_char)
            time.sleep(duration)
            pydirectinput.keyUp(key_char)
        except Exception:
            pass
        
    def release_all(self):
        """释放所有记录在案的被按下的键 (安全保护)"""
        for key in list(self.pressed_keys):
            self.key_up(key)

    def mouse_click(self, x=None, y=None):
        """模拟鼠标左键点击，用于结算界面点击关闭"""
        try:
            if x is not None and y is not None:
                pydirectinput.click(x, y)
            else:
                pydirectinput.click()
        except Exception:
            pass

    def check_hotkey(self, hotkey_str):
        """检测快捷键是否按下，如 'f9'"""
        return keyboard.is_pressed(hotkey_str)
