"""
smart_house.py — 智能家居设备模拟核心模块

本模块实现了一套纯 Python 的智能家居设备模拟系统，使用字典和函数引用来模拟类继承关系，
无需依赖任何外部框架，展示了一种轻量级的对象系统设计模式。
"""


# ==================== 全局设备列表 ====================
devices = []  # 存储所有已创建设备实例的全局列表


# ==================== 辅助工具函数 ====================
def clear_devices():
    """清空全局设备列表，用于测试场景之间的隔离。"""
    global devices
    devices = []
    print("[DEBUG] 所有设备已清空")


def make(cls, name, location, base_power, status, *args):
    """
    创建设备实例的工厂函数。

    参数:
        cls: 设备类描述符（Light, Thermostat 或 Camera）
        name: 设备名称
        location: 设备位置
        base_power: 基础功耗（瓦特）
        status: 设备状态（"on" 或 "off"）
        *args: 特定设备类型的额外参数（Light的亮度级别、Thermostat的温控范围等）

    返回:
        创建的设备实例字典，同时自动追加到全局 devices 列表中
    """
    # 参数验证
    if status not in ["on", "off"]:
        raise ValueError(f"无效状态: {status}，必须为 'on' 或 'off'")
    if not isinstance(base_power, (int, float)) or base_power < 0:
        raise ValueError(f"功耗必须为非负数，当前值: {base_power}")
    if not isinstance(name, str) or not name:
        raise ValueError("设备名称不能为空")

    # 调用特定类的实例化函数
    if cls["name"] == "Light":
        instance = _make_light(name, location, base_power, status, *args)
    elif cls["name"] == "Thermostat":
        instance = _make_thermostat(name, location, base_power, status, *args)
    elif cls["name"] == "Camera":
        instance = _make_camera(name, location, base_power, status, *args)
    else:
        raise TypeError(f"未知设备类型: {cls}")

    devices.append(instance)
    return instance


def call(obj, method_name, **kwargs):
    """
    动态调用对象的方法。

    参数:
        obj: 目标对象（设备实例字典）
        method_name: 要调用的方法名（字符串）
        **kwargs: 传递给方法的参数

    返回:
        方法的返回值
    """
    method = obj["methods"].get(method_name)
    if method is None:
        raise AttributeError(f"对象没有 '{method_name}' 方法")
    return method(obj, **kwargs)


# ==================== 设备类定义（使用字典作为"类"描述符） ====================

Light = {
    "name": "Light",
    "methods": {
        "get_power_consumption": lambda self: self["_base_power"] * (self["_brightness"] / 100) if self["_status"] == "on" else 0,
        "set_brightness": lambda self, brightness: _update_attr(self, "_brightness", brightness, 0, 100),
        "toggle": lambda self: _update_attr(self, "_status", "off" if self["_status"] == "on" else "on"),
        "get_description": lambda self: f"{self['_name']} (Light) at {self['_location']}, status: {self['_status']}, brightness: {self['_brightness']}%"
    }
}

Thermostat = {
    "name": "Thermostat",
    "methods": {
        "get_power_consumption": lambda self: self["_base_power"] * abs(self["_target_temp"] - self["_current_temp"]) if self["_status"] == "on" else 0,
        "set_target_temp": lambda self, temp: _update_attr(self, "_target_temp", temp, 10, 35),
        "set_current_temp": lambda self, temp: _update_attr(self, "_current_temp", temp, -10, 50),
        "toggle": lambda self: _update_attr(self, "_status", "off" if self["_status"] == "on" else "on"),
        "get_description": lambda self: f"{self['_name']} (Thermostat) at {self['_location']}, status: {self['_status']}, target: {self['_target_temp']}°C, current: {self['_current_temp']}°C"
    }
}

Camera = {
    "name": "Camera",
    "methods": {
        "get_power_consumption": lambda self: self["_base_power"] if self["_status"] == "on" else 0,
        "record_video": lambda self, duration: f"录制了 {duration} 秒视频，保存至 {self['_storage_location']}",
        "toggle": lambda self: _update_attr(self, "_status", "off" if self["_status"] == "on" else "on"),
        "get_description": lambda self: f"{self['_name']} (Camera) at {self['_location']}, status: {self['_status']}, resolution: {self['_resolution']}MP"
    }
}


# ==================== 连接能力 Mixin（可连接设备的行为） ====================
Connectable = {
    "name": "Connectable",
    "methods": {
        "connect": lambda self: _update_attr(self, "_connected", True),
        "disconnect": lambda self: _update_attr(self, "_connected", False),
        "is_connected": lambda self: self.get("_connected", False)
    }
}


# ==================== SmartHouse 管理接口 ====================
def create_SmartHouseManagement(name):
    """
    创建智能家居管理接口对象。

    参数:
        name: 管理系统名称

    返回:
        包含管理方法的字典对象
    """
    return {
        "_name": name,
        "methods": {
            "calculate_total_power_consumption": lambda self: sum(
                call(device, "get_power_consumption") for device in devices
            ),
            "get_all_device_description": lambda self: [call(device, "get_description") for device in devices],
            "get_all_connected_device": lambda self: [device for device in devices if call(device, "is_connected")],
            "get_device_count_by_type": lambda self, device_type: sum(1 for d in devices if d.get("_type") == device_type)
        }
    }


# ==================== 内部辅助函数 ====================
def _make_light(name, location, base_power, status, brightness=100):
    """创建灯光设备实例。"""
    _validate_brightness(brightness)
    return {
        "_type": "Light",
        "_name": name,
        "_location": location,
        "_base_power": base_power,
        "_status": status,
        "_brightness": brightness,
        "methods": Light["methods"]
    }


def _make_thermostat(name, location, base_power, status, target_temp=22, current_temp=20):
    """创建温控器设备实例。"""
    _validate_temperature(target_temp, "目标温度")
    _validate_temperature(current_temp, "当前温度")
    return {
        "_type": "Thermostat",
        "_name": name,
        "_location": location,
        "_base_power": base_power,
        "_status": status,
        "_target_temp": target_temp,
        "_current_temp": current_temp,
        "methods": Thermostat["methods"]
    }


def _make_camera(name, location, base_power, status, resolution=8):
    """创建摄像头设备实例，支持连接能力。"""
    if not isinstance(resolution, (int, float)) or resolution <= 0:
        raise ValueError("分辨率必须为正数")
    instance = {
        "_type": "Camera",
        "_name": name,
        "_location": location,
        "_base_power": base_power,
        "_status": status,
        "_resolution": resolution,
        "_storage_location": f"/recordings/{name.replace(' ', '_')}",
        "_connected": False,
        "methods": {**Camera["methods"], **Connectable["methods"]}
    }
    return instance


def _update_attr(obj, attr, value, min_val=None, max_val=None):
    """通用的属性更新辅助函数，支持范围验证。"""
    if min_val is not None and value < min_val:
        raise ValueError(f"{attr} 不能小于 {min_val}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{attr} 不能大于 {max_val}")
    obj[attr] = value
    return value


def _validate_brightness(brightness):
    """验证亮度值范围。"""
    if not isinstance(brightness, (int, float)) or brightness < 0 or brightness > 100:
        raise ValueError(f"亮度必须在 0-100 之间，当前值: {brightness}")


def _validate_temperature(temp, label):
    """验证温度值范围。"""
    if not isinstance(temp, (int, float)) or temp < -10 or temp > 50:
        raise ValueError(f"{label} 必须在 -10 到 50 之间，当前值: {temp}")


# ==================== 命令行演示入口 ====================
if __name__ == "__main__":
    print("=== 智能家居模拟系统演示 ===\n")

    clear_devices()

    # 创建各类设备
    light = make(Light, "书桌台灯", "书房", 50, "on", 75)
    thermostat = make(Thermostat, "客厅温控器", "客厅", 1000, "on", 22, 20)
    camera = make(Camera, "大门摄像头", "玄关", 10, "off", 5)

    print(f"已创建 {len(devices)} 个设备\n")

    # 连接摄像头
    call(camera, "connect")
    print(f"摄像头已连接: {call(camera, 'is_connected')}")

    # 操作设备
    call(light, "set_brightness", brightness=50)
    call(thermostat, "set_target_temp", temp=24)
    call(camera, "toggle")

    # 创建管理接口
    manager = create_SmartHouseManagement("我家")

    # 输出设备描述
    print("\n=== 所有设备信息 ===")
    for desc in call(manager, "get_all_device_description"):
        print(f"  {desc}")

    # 输出总功耗
    total_power = call(manager, "calculate_total_power_consumption")
    print(f"\n总功耗: {total_power} W")