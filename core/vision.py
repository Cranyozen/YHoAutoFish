import cv2
import numpy as np
import os

class VisionCore:
    def __init__(self):
        # 初始化默认的HSV阈值，后续可由GUI配置传入覆盖
        self.hsv_config = {
            "green": {"min": [40, 50, 50], "max": [80, 255, 255]},
            "yellow": {"min": [15, 100, 100], "max": [35, 255, 255]}
        }
        self._template_cache = {}
        self._processed_template_cache = {}
        
    def update_hsv_config(self, color_name, min_val, max_val):
        """用于GUI动态调节HSV参数"""
        if color_name in self.hsv_config:
            self.hsv_config[color_name]["min"] = min_val
            self.hsv_config[color_name]["max"] = max_val

    def _read_template(self, template_path):
        path = os.fspath(template_path)
        if path in self._template_cache:
            return self._template_cache[path]

        if not os.path.exists(path):
            self._template_cache[path] = None
            return None

        template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)
        self._template_cache[path] = template
        return template

    def _to_gray(self, image):
        if image is None:
            return None
        if len(image.shape) == 2:
            return image.copy()
        if len(image.shape) == 3 and image.shape[2] == 4:
            alpha_channel = image[:, :, 3]
            rgb_channels = image[:, :, :3]
            background = np.zeros_like(rgb_channels, dtype=np.uint8)
            alpha_factor = alpha_channel[:, :, np.newaxis] / 255.0
            bgr = (rgb_channels * alpha_factor + background * (1 - alpha_factor)).astype(np.uint8)
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def _prepare_for_match(self, image, use_edge=False, use_binary=False, binary_threshold=200):
        gray = self._to_gray(image)
        if gray is None:
            return None
        if use_binary:
            _, gray = cv2.threshold(gray, binary_threshold, 255, cv2.THRESH_BINARY)
        elif use_edge:
            gray = cv2.Canny(gray, 50, 150)
        return gray

    def _template_for_match(self, template_path, use_edge=False, use_binary=False, binary_threshold=200):
        path = os.fspath(template_path)
        cache_key = (path, bool(use_edge), bool(use_binary), int(binary_threshold))
        if cache_key in self._processed_template_cache:
            return self._processed_template_cache[cache_key]

        template = self._read_template(path)
        if template is None:
            print(f"[Vision] 无法解析图片数据: {path}")
            self._processed_template_cache[cache_key] = None
            return None

        prepared = self._prepare_for_match(template, use_edge=use_edge, use_binary=use_binary, binary_threshold=binary_threshold)
        self._processed_template_cache[cache_key] = prepared
        return prepared

    def _build_scales(self, scale_range=None, scale_steps=11):
        if scale_range is None:
            low, high = 0.5, 1.5
        else:
            low, high = float(scale_range[0]), float(scale_range[1])
        if low > high:
            low, high = high, low
        low = max(0.20, low)
        high = max(low, min(4.00, high))
        steps = max(1, int(scale_steps))
        if steps == 1 or abs(high - low) < 0.001:
            return [low]
        return list(np.linspace(high, low, steps))

    def find_template(
        self,
        screen_img,
        template_path,
        threshold=0.75,
        use_edge=False,
        use_binary=False,
        scale_range=None,
        scale_steps=11,
        binary_threshold=200,
    ):
        """
        在屏幕截图中寻找模板图片 (支持中文路径)
        use_edge: 是否使用 Canny 边缘检测匹配（排除光照干扰）
        use_binary: 是否使用二值化提取高亮特征匹配（适用于白天水面强光下的纯白 UI 图标）
        返回 (x, y) 坐标，如果没有找到返回 (None, None)
        """
        try:
            screen_gray = self._prepare_for_match(
                screen_img,
                use_edge=use_edge,
                use_binary=use_binary,
                binary_threshold=binary_threshold,
            )
            template_gray = self._template_for_match(
                template_path,
                use_edge=use_edge,
                use_binary=use_binary,
                binary_threshold=binary_threshold,
            )

            if screen_gray is None or template_gray is None:
                return None, 0.0
            
            best_match = None
            best_val = -1
            best_loc = None
            
            for scale in self._build_scales(scale_range=scale_range, scale_steps=scale_steps):
                # 缩放模板
                width = int(template_gray.shape[1] * scale)
                height = int(template_gray.shape[0] * scale)
                
                # 如果缩放后的模板比截图还要大，就跳过
                if width < 4 or height < 4 or width > screen_gray.shape[1] or height > screen_gray.shape[0]:
                    continue

                interpolation = cv2.INTER_NEAREST if use_binary else (cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
                resized_template = cv2.resize(template_gray, (width, height), interpolation=interpolation)
                if use_binary:
                    _, resized_template = cv2.threshold(resized_template, 127, 255, cv2.THRESH_BINARY)
                if float(np.std(resized_template)) < 1.0:
                    continue
                
                # 进行匹配
                res = cv2.matchTemplate(screen_gray, resized_template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_match = resized_template

            if best_val >= threshold and best_match is not None:
                h, w = best_match.shape[:2]
                center_x = best_loc[0] + w // 2
                center_y = best_loc[1] + h // 2
                return (center_x, center_y), best_val
                
            return None, best_val
        except Exception as e:
            print(f"[Vision] Template matching error: {e}")
            return None, 0.0

    def find_best_template(self, screen_img, template_paths, threshold=0.75, **kwargs):
        """在多个模板中返回置信度最高的匹配。"""
        best_loc = None
        best_conf = -1.0
        best_path = None

        for template_path in template_paths or []:
            loc, conf = self.find_template(screen_img, template_path, threshold=threshold, **kwargs)
            if conf > best_conf:
                best_loc = loc
                best_conf = conf
                best_path = template_path

        if best_loc is not None and best_conf >= threshold:
            return best_loc, best_conf, best_path
        return None, best_conf, best_path

    def analyze_fishing_bar(self, roi_img):
        """
        [极简防抖重构版]
        解析上方耐力条区域，提取绿条(目标)和黄条(游标)的中心X坐标。
        抛弃了不可靠的 HSV 颜色空间，直接通过灰度和亮度阈值定位高亮的游标。
        """
        if roi_img is None or roi_img.size == 0:
            return None, None, roi_img
            
        # ==========================================
        # 根据主程序的精确 ROI 截取，这里不再需要进行二次裁剪或涂黑处理
        # 直接使用 roi_img 进行 HSV 分析
        # ==========================================
        
        debug_img = roi_img.copy()
        
        # 1. 提取黄色游标 (高亮 + 黄色特征)
        # 将图像转换为 HSV 图，提取黄色范围
        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        
        # 精准黄色 HSV 范围 (H: 20-40, S: 100-255, V: 200-255)
        lower_yellow = np.array([20, 100, 200])
        upper_yellow = np.array([40, 255, 255])
        cursor_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # 2. 提取绿色目标区域 (中等亮度绿条)
        # 恢复对绿色色相的限制，防止提取到蓝天或白云，同时放宽饱和度
        # H: 40(偏黄绿) 到 90(偏青绿)
        lower_green = np.array([40, 40, 60])
        upper_green = np.array([90, 255, 255])
        target_mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # 增强形态学处理：绿条可能有半透明或者被游标遮挡，导致断裂
        # 使用闭运算连接断裂的绿条，确保提取的中心更稳定
        kernel = np.ones((3, 3), np.uint8)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, kernel)
        cursor_mask = cv2.morphologyEx(cursor_mask, cv2.MORPH_CLOSE, kernel)
        
        # 对于绿条，不进行极其严格的形态学限制，因为它可能因为半透明被截断
        target_info = self._get_center_x(target_mask, is_vertical=False, strict_shape=False, return_width=True)
        cursor_info = self._get_center_x(cursor_mask, is_vertical=True, strict_shape=True, return_width=True)
        
        target_x, target_w = target_info if target_info else (None, None)
        cursor_x, cursor_w = cursor_info if cursor_info else (None, None)
        
        # 在 Debug 图像上画线
        if target_x is not None:
            # 画出绿条的中心线和宽度范围
            cv2.line(debug_img, (target_x, 0), (target_x, debug_img.shape[0]), (0, 255, 0), 2)
            cv2.rectangle(debug_img, (target_x - target_w//2, 0), (target_x + target_w//2, debug_img.shape[0]), (0, 100, 0), 1)
        if cursor_x is not None:
            cv2.line(debug_img, (cursor_x, 0), (cursor_x, debug_img.shape[0]), (0, 255, 255), 2)
            
        return target_x, cursor_x, target_w, debug_img

    def _get_center_x(self, mask, is_vertical=False, strict_shape=True, return_width=False):
        """从二值化掩码中找到最大的合法轮廓，并返回中心X坐标 (以及可选的宽度)"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None
        
        # 按照面积从大到小排序，只取最大的那个，防止被背景的小噪点干扰
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            
            # 忽略过小的噪点
            if area < 5: 
                continue
                
            if strict_shape:
                # 宽容的形态学过滤：
                # 黄色游标 (is_vertical=True) 应该是竖着的，高大于宽，放宽要求
                if is_vertical and w > h * 1.8: 
                    continue
                    
                # 绿色目标条 (is_vertical=False) 应该是横着的，宽大于高
                if not is_vertical and h > w * 1.8:
                    continue
                
            if return_width:
                return x + w // 2, w
            return x + w // 2
            
        return None
