# core/settings.py
import json
import os

SETTINGS_FILE = 'settings.json'

def save_setting(key, value):
    """保存单个设置项到 JSON 文件"""
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            # 如果文件存在但为空或损坏，则忽略
            pass
    
    settings[key] = value
    
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        # print(f"[Settings] 已保存 '{key}': {value}")
        pass
    except IOError as e:
        # print(f"[Settings] 错误：无法写入设置文件 {SETTINGS_FILE}: {e}")
        pass

def load_setting(key, default=None):
    """从 JSON 文件加载单个设置项"""
    if not os.path.exists(SETTINGS_FILE):
        return default
        
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            value = settings.get(key, default)
            # print(f"[Settings] 已加载 '{key}': {value}")
            pass
            return value
    except (json.JSONDecodeError, IOError) as e:
        # print(f"[Settings] 错误：无法读取设置文件 {SETTINGS_FILE}: {e}")
        pass
        return default
