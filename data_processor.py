from threading import Thread, Lock
import time
import logging
from shared_data import TelemetryData  # 更名后的数据模块

class DataProcessor:
    def __init__(self, vibration_ctrl):
        self.vib_ctrl = vibration_ctrl
        self.running = False
        self.thread = None
        self.last_ammo = 0
        self.last_counter = 0
        self.lock = Lock()
        self.last_data_hash = None
        self.buffer_size = 4
        self.onground_buffer = []
        self.ammo_buffer = []

    def _check_onground(self, current_data):
        """新增振动开关检查"""
        if not current_data.get('VIBRATION_SETTINGS', {}).get('OnGround', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        if 'OnGround' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        self.onground_buffer.append(current_data['OnGround'])
        if len(self.onground_buffer) > self.buffer_size:
            self.onground_buffer = self.onground_buffer[-self.buffer_size:]
        
        unique_values = set(self.onground_buffer)
        if len(unique_values) > 1:
            return {'active': True, 'left': 1.0, 'right': 0.0}
        return {'active': False, 'left': 0.0, 'right': 0.0}

    def _check_bomb_status(self, current_data):
        """新增振动开关检查"""
        if not current_data.get('VIBRATION_SETTINGS', {}).get('total_bomb', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        if 'total_bomb' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        current_ammo = current_data['total_bomb']
        if hasattr(self, 'previous_ammo'):
            self.ammo_buffer.append(current_ammo < self.previous_ammo)
        else:
            self.ammo_buffer.append(False)  
        
        if len(self.ammo_buffer) > 5:
            self.ammo_buffer = self.ammo_buffer[-5:]
        
        self.previous_ammo = current_ammo
        trigger = any(self.ammo_buffer)
        return {'active': trigger, 'left': 0.0, 'right': 0.5 if trigger else 0.0}

    def _check_ammo(self, current_data):
        """机炮震动，新增振动开关检查"""
        if not current_data.get('VIBRATION_SETTINGS', {}).get('AMMO', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        if 'AMMO' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        current_ammo = current_data['AMMO']
        if current_ammo < self.last_ammo:
            self.last_ammo = current_ammo
            return {'active': True, 'left': 1.0, 'right': 1.0}
        self.last_ammo = current_ammo
        return {'active': False, 'left': 0.0, 'right': 0.0}

    def _check_gforce(self, current_data):
        """G震动，使用配置中的G阈值"""
        if not current_data.get('VIBRATION_SETTINGS', {}).get('G', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        if 'G' not in current_data or 'G_THRESHOLD' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        # 使用动态配置的G阈值
        g = current_data['G']
        g_threshold = current_data['G_THRESHOLD']
        if g > g_threshold or g < -4:
            return {'active': True, 'left': 0.5, 'right': 0.5}
        return {'active': False, 'left': 0.0, 'right': 0.0}

    def _check_speedbrake(self, current_data):
        """根据新表格的震动强度映射（Python类方法版）"""
        vib_settings = current_data.get('VIBRATION_SETTINGS', {})
        tas = current_data.get('TAS', 0)  # 单位：节
        speedbrake = current_data.get('SpeedBrake', 0)  # 单位：百分比0-100
        
        # 1. 振动总开关检查
        if not vib_settings.get('SpeedBrake', True) or speedbrake == 0:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        # 2. 震动强度映射表（完全匹配表格数据）
        vibration_matrix = {
            # 速度区间索引: [0%档, 20%档, 40%档, 60%档, 80%+档]
            0: [0.00, 0.00, 0.00, 0.00, 0.00],   # 0-50节
            1: [0.01, 0.01, 0.01, 0.02, 0.02],   # 50-200节
            2: [0.01, 0.02, 0.03, 0.04, 0.05],   # 200-400节
            3: [0.02, 0.04, 0.06, 0.08, 0.10]    # 400+节
        }
        
        # 3. 确定速度区间
        band_idx = 3  # 默认最高速度区间
        if tas < 50:
            band_idx = 0
        elif 50 <= tas < 200:
            band_idx = 1
        elif 200 <= tas < 400:
            band_idx = 2
        
        # 4. 计算减速板档位（0-4对应0%/20%/40%/60%/80%+）
        sb_level = min(int(speedbrake // 20), 4)
        
        # 5. 获取震动强度
        vib_strength = vibration_matrix[band_idx][sb_level]
        
        return {
            'active': vib_strength > 0,
            'left': vib_strength,
            'right': 0.0  # 右马达保持关闭
        }

    def _check_afterburner(self, current_data):
        """新增右加力燃烧室震动检查"""
        # 检查震动开关设置
        if not current_data.get('VIBRATION_SETTINGS', {}).get('AfterburnerRight', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        # 参数有效性验证
        if 'AB_R' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        ab_right = current_data['AB_R']
        if not (0 <= ab_right <= 1):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        # 分区间设置震动强度
        if ab_right == 0:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        elif 0 < ab_right <= 0.2:
            return {'active': True, 'left': 0.0, 'right': 0.1}
        elif 0.2 < ab_right <= 0.4:
            return {'active': True, 'left': 0.0, 'right': 0.2}
        elif 0.4 < ab_right <= 0.6:
            return {'active': True, 'left': 0.0, 'right': 0.3}
        elif 0.6 < ab_right <= 0.8:
            return {'active': True, 'left': 0.0, 'right': 0.4}
        else:
            return {'active': True, 'left': 0.0, 'right': 0.5}

    def _check_counter(self, current_data):
        """检测干扰弹数量减少并触发左马达震动"""
        # 检查震动开关是否开启
        if not current_data.get('VIBRATION_SETTINGS', {}).get('COUNTER', True):
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        if 'COUNTER' not in current_data:
            return {'active': False, 'left': 0.0, 'right': 0.0}
        
        current_counter = current_data['COUNTER']
        
        # 初始化缓冲区（如果不存在）
        if not hasattr(self, 'counter_buffer'):
            self.counter_buffer = []
        
        # 检测计数器是否减少
        if hasattr(self, 'last_counter'):
            self.counter_buffer.append(current_counter < self.last_counter)
        else:
            self.counter_buffer.append(False)
        
        # 保持缓冲区长度为5（约500ms）
        if len(self.counter_buffer) > 3:
            self.counter_buffer = self.counter_buffer[-3:]
        
        # 只要有任意一次减少记录就保持震动
        trigger = any(self.counter_buffer)
        
        # 更新上一次计数器值
        self.last_counter = current_counter
        
        return {
            'active': trigger,
            'left': 0.2 if trigger else 0.0,
            'right': 0.0
        }

    def _get_vibration_level(self, current_data):
        """根据配置动态过滤条件"""
        vib_checks = [
            self._check_ammo(current_data),
            self._check_gforce(current_data),
            self._check_speedbrake(current_data),
            self._check_onground(current_data),
            self._check_bomb_status(current_data),
            self._check_afterburner(current_data),
            self._check_counter(current_data)
        ]
        
        active = any(check['active'] for check in vib_checks)
        left = max(check['left'] for check in vib_checks)
        right = max(check['right'] for check in vib_checks)
        
        return {'active': active, 'left': left, 'right': right}

    def _process_loop(self):
        while self.running:
            try:
                current_data = TelemetryData.get_current()
                current_hash = str(current_data) if current_data else None
                
                if current_hash != self.last_data_hash:
                    vib_level = self._get_vibration_level(current_data or {})
                    self.vib_ctrl.set_vibration_flag(
                        vib_level['active'],
                        vib_level['left'],
                        vib_level['right']
                    )
                    self.last_data_hash = current_hash
                    
                    # if current_data:
                    #     print(f"处理数据: {current_data} -> 震动: {vib_level}")
                
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"处理循环异常: {e}")
                time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()