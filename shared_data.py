from threading import Lock
from datetime import datetime, timedelta
import copy
import json
import os
import sys

class ConfigManager:
    _config = None

    @classmethod
    def load_config(cls, config_path=None):
        try:
            # 获取 EXE 或脚本所在目录
            if getattr(sys, 'frozen', False):
                # 打包为 EXE 时，sys.executable 是 EXE 路径
                base_dir = os.path.dirname(sys.executable)
            else:
                # 开发时，__file__ 是脚本路径
                base_dir = os.path.dirname(os.path.abspath(__file__))

            # 自动构建配置文件路径
            if not config_path:
                config_path = os.path.join(base_dir, "aircraft_config.json")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._config = json.load(f)
            
            # 预处理飞机配置
            default = cls._config["DEFAULT"]
            if "AIRCRAFTS" in cls._config:
                for aircraft in cls._config["AIRCRAFTS"]:
                    aircraft_config = cls._config["AIRCRAFTS"][aircraft]
                    
                    # 深度合并配置
                    merged = {
                        **default,
                        **aircraft_config,
                        "vibration_settings": {
                            **default["vibration_settings"],
                            **aircraft_config.get("vibration_settings", {})
                        },
                        "corrections": {
                            **default["corrections"],
                            **aircraft_config.get("corrections", {})
                        }
                    }
                    cls._config["AIRCRAFTS"][aircraft] = merged

        except Exception as e:
            raise RuntimeError(f"配置加载失败: {str(e)}\n"
                             f"完整路径: {config_path}\n"
                             f"工作目录: {os.getcwd()}")

    @classmethod
    def get_config(cls, aircraft_name):
        if not cls._config:
            cls.load_config()
            
        return cls._config.get("AIRCRAFTS", {}).get(
            aircraft_name,
            cls._config.get("DEFAULT", {})
        )

class TelemetryData:
    _data = None
    _lock = Lock()
    _last_update = None
    _timeout = timedelta(seconds=3)  # 数据过期时间（3秒）

    @classmethod
    def _apply_corrections(cls, new_data):
        """实施数据修正"""
        if not ConfigManager._config.get("ENABLE_CORRECTIONS", False):
            return
            
        aircraft_name = new_data.get('NAME')
        config = ConfigManager.get_config(aircraft_name)
        
        if config.get("corrections", {}).get("active", False):
            for key, value in config.get("corrections", {}).get("overrides", {}).items():
                if key in new_data:
                    new_data[key] = value

    @classmethod
    def update(cls, raw_data):
        with cls._lock:
            try:
                items = [item.strip() for item in raw_data.split(',') if '=' in item]
                new_data = {'timestamp': datetime.now()}
                
                for item in items:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.split('%')[0].strip() if '%' in value else value.strip()
                    
                    try:
                        if key == 'NAME':
                            new_data[key] = value
                            config = ConfigManager.get_config(value)
                            new_data.update({
                                'G_THRESHOLD': config.get('g_threshold', 4.0),
                                'VIBRATION_SETTINGS': config.get('vibration_settings', {})
                            })
                        elif key in ['TIME', 'G', 'AB_R']:
                            new_data[key] = float(value)
                        elif key in ['AMMO', 'SpeedBrake', 'OnGround', 'total_bomb', 'TAS', 'COUNTER', 'RWR']:
                            new_data[key] = int(float(value)) if value.replace('.','',1).isdigit() else 0
                    except ValueError:
                        continue
                
                cls._apply_corrections(new_data)
                cls._data = new_data
                cls._last_update = datetime.now()
                
            except Exception as e:
                print(f"数据更新异常: {e}")

    @classmethod
    def get_current(cls):
        with cls._lock:
            # 如果没有数据或数据过期，返回归零数据
            if cls._data is None or (cls._last_update and (datetime.now() - cls._last_update) > cls._timeout):
                aircraft_name = cls._data.get('NAME') if cls._data else None
                config = ConfigManager.get_config(aircraft_name) if aircraft_name else {}
                
                # 构造归零数据，保留配置相关字段
                zeroed_data = {
                    'timestamp': datetime.now(),
                    'NAME': aircraft_name if aircraft_name else '',
                    'G_THRESHOLD': config.get('g_threshold', 4.0),
                    'VIBRATION_SETTINGS': config.get('vibration_settings', {}),
                    'TIME': 0.0,
                    'G': 0.0,
                    'AB_R': 0.0,
                    'AMMO': 0,
                    'SpeedBrake': 0,
                    'OnGround': 0,
                    'total_bomb': 0,
                    'TAS': 0,
                    'COUNTER': 0,
                    'RWR': 0
                }
                return copy.deepcopy(zeroed_data)
            
            return copy.deepcopy(cls._data)

# 正确初始化位置：在模块加载时初始化
ConfigManager.load_config()