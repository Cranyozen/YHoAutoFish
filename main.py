import sys
import os

# 确保能找到 core 和 gui 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.app import App

if __name__ == '__main__':
    # 初始化GUI应用
    app = App()
    
    # 进入主事件循环
    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"致命错误: {e}")
    finally:
        # 清理资源
        if hasattr(app, 'sm'):
            app.sm.stop()
        os._exit(0)
