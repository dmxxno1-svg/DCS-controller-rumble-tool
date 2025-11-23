from XInput import set_vibration, get_connected
import threading
import time

class VibrationController:
    def __init__(self, controller_id=0):
        self.controller_id = controller_id
        self._stop_flag = False
        self.connected = get_connected()[self.controller_id]
        self.vibration_flag = {
            'active': False,
            'left': 0.0,
            'right': 0.0
        }
        self.lock = threading.Lock()
        self.event = threading.Event()  # 创建一个 Event 对象
        self.control_thread = threading.Thread(target=self._vibration_control_loop)
        self.control_thread.start()

    def _vibration_control_loop(self):
        last_adjust_time = time.time()
        adjust_up = True  # 控制震动强度是增加还是减少
        while not self._stop_flag:
            with self.lock:
                active = self.vibration_flag['active']
                left = self.vibration_flag['left']
                right = self.vibration_flag['right']
            
            # 每 0.1 秒调整震动强度，仅对非零马达应用变化
            if time.time() - last_adjust_time >= 0.1:
                adjust_value = 0.01 if adjust_up else -0.01
                if left > 0:
                    left = max(0.0, min(1.0, left + adjust_value))
                if right > 0:
                    right = max(0.0, min(1.0, right + adjust_value))
                adjust_up = not adjust_up  # 切换调整方向
                last_adjust_time = time.time()
            
            if active and self.connected:
                set_vibration(self.controller_id, left, right)
            else:
                set_vibration(self.controller_id, 0.0, 0.0)
            
            self.event.wait(0.1)  # 100ms 更新间隔

    def set_vibration_flag(self, active: bool, left: float, right: float):
        """设置震动标识"""
        with self.lock:
            self.vibration_flag['active'] = active
            self.vibration_flag['left'] = left
            self.vibration_flag['right'] = right

    def stop(self):
        self._stop_flag = True
        self.control_thread.join()
        set_vibration(self.controller_id, 0.0, 0.0)