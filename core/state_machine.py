import time
import threading
import queue
import cv2
import os

from core.window_manager import WindowManager
from core.screen_capture import ScreenCapture
from core.controller import Controller
from core.vision import VisionCore

class StateMachine:
    STATE_IDLE = 0
    STATE_WAITING = 1
    STATE_FISHING = 2
    STATE_RESULT = 3
    STATE_FAILED = 4
    STATE_PAUSED = 5
    
    def __init__(self, log_queue=None, debug_queue=None, config=None):
        self.log_queue = log_queue
        self.debug_queue = debug_queue
        
        self.wm = WindowManager()
        self.sc = ScreenCapture()
        self.ctrl = Controller()
        self.vis = VisionCore()
        
        self.is_running = False
        self.current_state = self.STATE_IDLE
        self.fishing_start_time = 0
        self.fishing_timeout = 180 # 3分钟超时防卡死
        self.fish_count = 0
        self.total_runtime = 0
        self.start_timestamp = 0
        
        # 参数配置 (后续可由 GUI 更新)
        self.config = config or {
            "t_hold": 15,       # 长按阈值像素
            "t_deadzone": 5,    # 死区像素
            "hotkey_start": 'f9',
            "hotkey_stop": 'f10',
            "debug_mode": True
        }
        
    def _log(self, msg):
        """线程安全的日志发送"""
        self.log_queue.put(msg)

    def start(self):
        """启动状态机"""
        if self.is_running: return
        self.is_running = True
        self.current_state = self.STATE_IDLE
        self.start_timestamp = time.time()
        self._log("钓鱼脚本启动中，正在寻找游戏窗口...")
        
        # 在独立线程运行主循环
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def stop(self):
        """停止状态机"""
        if not self.is_running: return
        self.is_running = False
        self.ctrl.release_all()
        self._log("钓鱼脚本已停止。")
        # 传递特定的控制指令给 GUI，让 GUI 恢复按钮状态
        self._log("CMD_STOP_UPDATE_GUI")

    def update_config(self, key, value):
        self.config[key] = value

    def _run_loop(self):
        # 初始化与绑定窗口
        if not self.wm.find_window():
            self._log("错误: 未找到游戏进程 HTGame.exe。请确保游戏正在运行。")
            # 通过队列通知 GUI 线程更新状态，而不是在这里直接改 self.is_running
            # 因为这会让 GUI 的 start_bot / stop_bot 按钮状态不同步
            self.stop()
            # 这里的 return 会让线程结束
            return
            
        self._log("成功绑定游戏窗口。")
        self.wm.set_foreground()
        time.sleep(1) # 等待窗口置顶完成
        
        # ROI 定义 (相对于客户区宽高)
        # 将 F 键的寻找范围扩大，以防止由于分辨率导致的右下角偏移
        ROI_F_BTN = (0.7, 0.7, 0.3, 0.3)
        self.roi_f_btn = ROI_F_BTN # 保存给其他状态使用
        
        # 恢复合理的高度范围，根据用户提供的精确比例进行定位：
        # 横向占比是30%到70% (X: 0.3, Width: 0.4)
        # 竖向占比是从5.56%到8.33% (Y: 0.0556, Height: 0.0277)
        ROI_FISHING_BAR = (0.3, 0.0556, 0.4, 0.0277) 
        
        ROI_CENTER_TEXT = (0.2, 0.2, 0.6, 0.5)
        
        # DEBUG 计数器，防止写爆硬盘
        debug_save_count = 0

        while self.is_running:
            # 1. 焦点保护机制
            if not self.wm.is_foreground():
                # 检查当前焦点是否是被我们自己的 Debug 窗口抢走了
                import win32gui
                fg_hwnd = win32gui.GetForegroundWindow()
                if win32gui.GetWindowText(fg_hwnd) == "Fishing Bar Tracker (Debug)":
                    # 如果是被 Debug 窗口抢走的，不要暂停按键，尝试切回去
                    self.wm.set_foreground()
                else:
                    self._log("警告: 游戏窗口失去焦点，暂停按键发送。")
                    self.ctrl.release_all()
                    time.sleep(1)
                    continue
                
            # 2. 获取实时窗口坐标 (防止窗口被拖动)
            rect = self.wm.get_client_rect()
            if not rect:
                self._log("获取窗口坐标失败，请不要最小化游戏。")
                time.sleep(1)
                continue
                
            # 3. 状态分发
            if self.current_state == self.STATE_IDLE:
                self._handle_idle(rect, ROI_F_BTN)
            elif self.current_state == self.STATE_WAITING:
                self._handle_waiting(rect, ROI_CENTER_TEXT)
            elif self.current_state == self.STATE_FISHING:
                self._handle_fishing(rect, ROI_FISHING_BAR)
            elif self.current_state == self.STATE_RESULT:
                self._handle_result(rect)
            elif self.current_state == self.STATE_FAILED:
                self._handle_failed()
                
            # 控制基础循环帧率
            time.sleep(0.01)
            
        self.sc.close()

    def _handle_idle(self, rect, roi):
        self._log("[待机] 正在检测右下角抛竿图标...")
        
        # 截取右下角 ROI
        btn_img = self.sc.capture_relative(rect, *roi)
        if btn_img is None: 
            time.sleep(1)
            return
            
        # DEBUG 计数器
        if not hasattr(self, '_debug_count'): self._debug_count = 0
        self._debug_count += 1
            
        # 找图匹配
        # 使用极低阈值 (0.45) 进行暴力兼容，只要形状类似 F 即可通过
        btn_path = os.path.join("assets", "F键图标.png")
        loc, conf = self.vis.find_template(btn_img, btn_path, threshold=0.45)
        
        if loc:
            self._log(f"[待机] 识别到 F 键图标 (置信度: {conf:.2f})，坐标: {loc}。准备抛竿。")
            self._log("[待机] > 正在向游戏发送 'F' 键点按指令 (150ms)...")
            self.ctrl.key_tap('F', duration=0.15)
            self._log("[待机] > 发送完成，等待 2 秒抛竿动画...")
            self.current_state = self.STATE_WAITING
            time.sleep(2) # 抛竿动画较长，防抖
        else:
            if self._debug_count % 10 == 0 and self._debug_count <= 30:
                cv2.imwrite("debug_f_btn_roi.png", btn_img)
                self._log(f"[排错] 抛竿图标匹配失败，最高置信度: {conf:.2f}。已保存当前截图至根目录 debug_f_btn_roi.png")
            time.sleep(0.5)

    def _handle_waiting(self, rect, roi):
        # 每隔一小段时间检测一次即可，不需要过高频率
        time.sleep(0.1) 
        
        text_img = self.sc.capture_relative(rect, *roi)
        if text_img is None: return
        
        text_path = os.path.join("assets", "上钩文字.png")
        loc, conf = self.vis.find_template(text_img, text_path, threshold=0.7)
        
        if loc:
            self._log(f"[等待] 识别到上钩提示 (置信度: {conf:.2f})，迅速按F！")
            self.ctrl.key_tap('F')
            self.fishing_start_time = time.time()
            self.current_state = self.STATE_FISHING
            time.sleep(1.5) # 进入溜鱼模式的过渡动画

    def _handle_fishing(self, rect, roi):
        # 超时保护
        if time.time() - self.fishing_start_time > self.fishing_timeout:
            self._log("[防卡死] 溜鱼超时，强制结束当前回合。")
            self.current_state = self.STATE_FAILED
            return

        # 截取耐力条 ROI
        bar_img = self.sc.capture_relative(rect, *roi)
        if bar_img is None: return
        
        target_x, cursor_x, target_w, debug_img = self.vis.analyze_fishing_bar(bar_img)
        
        # 核心：将 debug 图像通过安全队列发送给主线程，而不是在这里直接 imshow
        if self.config.get("debug_mode", True) and debug_img is not None:
            if self.debug_queue and self.debug_queue.qsize() < 2:
                # 放缩一下以便于观察
                show_img = cv2.resize(debug_img, (0, 0), fx=1.5, fy=1.5)
                self.debug_queue.put(show_img)
            
        # 核心修改：如果连续多次找不到耐力条，说明溜鱼结束（可能是成功结算，也可能是失败溜走）
        # 我们不能直接跳到结算，必须交给专门的仲裁逻辑，或者退回等待状态让找图逻辑接管
        if target_x is None or cursor_x is None:
            if not hasattr(self, '_missing_bar_count'): self._missing_bar_count = 0
            self._missing_bar_count += 1
            if self._missing_bar_count > 10:
                self._log("[溜鱼] 耐力条消失，停止溜鱼，进入结果判定...")
                self.ctrl.release_all()
                self._missing_bar_count = 0
                
                # 给游戏一点时间弹出结算或失败动画
                time.sleep(2.0)
                # 切回结果状态进行裁判
                self.current_state = self.STATE_RESULT 
            return
            
        self._missing_bar_count = 0 # 找到了就清零

        # -----------------------------------------------------
        # 优化版 PID 追踪算法 (防震荡、防脱离)
        # -----------------------------------------------------
        error = target_x - cursor_x
        abs_error = abs(error)
        
        # 提取绿条的半宽来作为死区参考，如果没有提取到，默认 15 像素
        dynamic_deadzone = max(10, int(target_w * 0.4)) if target_w else 15
        
        # 这里 t_hold 由用户配置或默认值提供，代表开始长按的阈值
        t_hold = self.config.get("t_hold", 25)
        
        actual_deadzone = dynamic_deadzone
        actual_hold = max(t_hold, actual_deadzone + 10)
        
        # 决定按键方向
        key_to_press = 'D' if error > 0 else 'A'
        key_to_release = 'A' if error > 0 else 'D'

        if abs_error <= actual_deadzone:
            # 在死区内，绝对安全，释放所有按键让其自然减速
            self.ctrl.release_all()
        else:
            if abs_error > actual_hold:
                # 偏离较大，长按加速追赶
                self.ctrl.key_up(key_to_release)
                self.ctrl.key_down(key_to_press)
            else:
                # 偏离中等，使用极短的点按进行微调 (高频微调)
                self.ctrl.release_all()
                # 动态计算点按时间 0.01 到 0.04秒，偏离越小，按得越轻
                tap_time = 0.01 + 0.03 * ((abs_error - actual_deadzone) / (actual_hold - actual_deadzone))
                self.ctrl.key_tap(key_to_press, tap_time)

    def _handle_result(self, rect):
        self._log("[结算] 正在检测钓鱼结果...")
        
        # 尝试检测是否有 F 键 (如果钓鱼失败，游戏会自动在一秒后恢复到带有 F 键的待机画面)
        btn_img = self.sc.capture_relative(rect, *self.roi_f_btn)
        if btn_img is not None:
            btn_path = os.path.join("assets", "F键图标.png")
            loc, conf = self.vis.find_template(btn_img, btn_path, threshold=0.45)
            
            if loc:
                self._log(f"[结算] 识别到抛竿图标 (置信度: {conf:.2f})，鱼儿溜走，已自动重置。")
                self.current_state = self.STATE_IDLE
                return

        # 如果没有识别到 F 键，说明很可能是成功的结算界面（需要手动点击关闭）
        self._log("[结算] 未识别到抛竿图标，判定为钓鱼成功！模拟点击空白区域关闭...")
        click_x = rect[0] + rect[2] // 2
        click_y = rect[1] + int(rect[3] * 0.8)
        self.ctrl.mouse_click(click_x, click_y)
        self.fish_count += 1
        self._log(f"[结算] 成功关闭结算界面。当前累计钓获: {self.fish_count} 条。等待抛竿...")
        time.sleep(2) # 等待关闭动画完成
        self.current_state = self.STATE_IDLE

    def _handle_failed(self):
        # 注意: 这里的“溜走了”如果用户提供了图片，建议也走 find_template
        # 目前暂时作为占位或使用超时跳出
        self._log("[失败/结束] 释放按键，等待复位。")
        self.ctrl.release_all()
        time.sleep(1.5)
        self.current_state = self.STATE_IDLE
