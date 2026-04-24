import mss
import numpy as np

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        
    def capture_roi(self, left, top, width, height):
        """
        截取屏幕上指定 ROI 区域，并返回 numpy (OpenCV BGR格式)
        参数为屏幕绝对坐标
        """
        monitor = {
            "top": int(top),
            "left": int(left),
            "width": int(width),
            "height": int(height)
        }
        
        # 获取图像，sct 返回 BGRA 格式
        sct_img = self.sct.grab(monitor)
        
        # 转换为 numpy 数组
        img_np = np.array(sct_img)
        
        # 抛弃 Alpha 通道 (BGRA -> BGR)，便于 OpenCV 处理
        return img_np[:, :, :3]
        
    def capture_relative(self, window_rect, rx, ry, rw, rh):
        """
        基于客户区窗口截取相对区域。
        例如 rx=0.5, ry=0.1, rw=0.2, rh=0.1 表示截取中心偏上的一块区域。
        window_rect: (left, top, width, height)
        """
        if not window_rect:
            return None
            
        w_left, w_top, w_width, w_height = window_rect
        
        abs_left = w_left + int(w_width * rx)
        abs_top = w_top + int(w_height * ry)
        abs_width = int(w_width * rw)
        abs_height = int(w_height * rh)
        
        return self.capture_roi(abs_left, abs_top, abs_width, abs_height)

    def close(self):
        """释放 mss 资源"""
        if self.sct:
            self.sct.close()
