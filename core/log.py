import logging


def setup_logging(log_queue=None) -> None:
    """配置全局日志系统。

    - 控制台输出所有 DEBUG+ 日志（格式含模块名与级别）。
    - 若提供 log_queue，则将 INFO+ 日志路由到 GUI 队列（仅消息正文）。

    可在 AppWindow.__init__ 中调用，此后所有模块的 logging 调用
    均自动路由到控制台和 GUI 日志面板。
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 避免重复添加控制台 handler
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, _QueueHandler)
               for h in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(console)

    if log_queue is not None:
        # 移除旧的 GUI queue handler，防止重复注册（如重启场景）
        for h in root.handlers[:]:
            if isinstance(h, _QueueHandler):
                root.removeHandler(h)
        gui = _QueueHandler(log_queue)
        gui.setLevel(logging.INFO)
        gui.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(gui)


class _QueueHandler(logging.Handler):
    """将日志记录放入队列供 GUI 消费。"""

    def __init__(self, queue):
        super().__init__()
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)
