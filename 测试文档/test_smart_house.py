"""
test_smart_house.py — 智能家居系统的单元测试集

本测试套件涵盖设备创建、功耗计算、方法调用、设备连接和管理接口等功能，
测试结果以 PASS/FAIL/ERROR 格式输出，同时输出详细日志供调试分析。
"""

from smart_house import (
    make, call, clear_devices, devices,
    Light, Thermostat, Camera, Connectable,
    create_SmartHouseManagement
)
import sys


# ==================== 测试辅助函数 ====================
def run_test(test_func):
    """运行单个测试并统计结果。"""
    try:
        test_func()
        print(f"✅ PASS: {test_func.__name__}")
        return True
    except AssertionError as e:
        print(f"❌ FAIL: {test_func.__name__} - {e}")
        return False
    except Exception as e:
        print(f"💥 ERROR: {test_func.__name__} - {type(e).__name__}: {e}")
        return False


# ==================== 测试场景 1: 设备创建与基础属性 ====================
def test_device_creation():
    """测试设备能否正确创建并初始化属性值。"""
    clear_devices()

    light = make(Light, "书桌台灯", "书房", 50, "on", 75)
    assert light is not None
    assert light["_name"] == "书桌台灯"
    assert light["_location"] == "书房"
    assert light["_base_power"] == 50
    assert light["_status"] == "on"
    assert light["_brightness"] == 75

    thermostat = make(Thermostat, "客厅温控器", "客厅", 1000, "on", 22, 20)
    assert thermostat["_target_temp"] == 22
    assert thermostat["_current_temp"] == 20

    camera = make(Camera, "大门摄像头", "玄关", 10, "off", 5)
    assert camera["_resolution"] == 5
    assert camera.get("_connected") is False

    assert len(devices) == 3


def test_device_creation_invalid_input():
    """测试设备创建时无效输入应抛出异常。"""
    clear_devices()

    try:
        make(Light, "", "书房", 50, "on", 75)
        assert False, "应该抛出空设备名异常"
    except ValueError:
        pass

    try:
        make(Light, "台灯", "书房", -10, "on", 75)
        assert False, "应该抛出负功耗异常"
    except ValueError:
        pass

    try:
        make(Light, "台灯", "书房", 50, "invalid_status", 75)
        assert False, "应该抛出无效状态异常"
    except ValueError:
        pass

    try:
        make(Light, "台灯", "书房", 50, "on", 150)
        assert False, "应该抛出亮度超出范围异常"
    except ValueError:
        pass


# ==================== 测试场景 2: 方法调用与动态行为 ====================
def test_light_functionality():
    """测试灯光设备的功能方法。"""
    clear_devices()
    light = make(Light, "书桌台灯", "书房", 50, "on", 75)

    initial_power = call(light, "get_power_consumption")
    assert initial_power == 50 * 0.75

    call(light, "set_brightness", brightness=50)
    assert light["_brightness"] == 50

    call(light, "toggle")
    assert light["_status"] == "off"
    assert call(light, "get_power_consumption") == 0


def test_thermostat_functionality():
    """测试温控设备的功能方法。"""
    clear_devices()
    thermostat = make(Thermostat, "客厅温控器", "客厅", 1000, "on", 22, 20)

    initial_power = call(thermostat, "get_power_consumption")
    assert initial_power == 1000 * 2

    call(thermostat, "set_target_temp", temp=24)
    assert thermostat["_target_temp"] == 24

    call(thermostat, "toggle")
    assert thermostat["_status"] == "off"
    assert call(thermostat, "get_power_consumption") == 0


def test_camera_functionality():
    """测试摄像头的功能和连接能力。"""
    clear_devices()
    camera = make(Camera, "大门摄像头", "玄关", 10, "off", 5)

    assert hasattr(camera["methods"], "connect")
    assert hasattr(camera["methods"], "disconnect")

    call(camera, "connect")
    assert call(camera, "is_connected") is True

    call(camera, "disconnect")
    assert call(camera, "is_connected") is False

    call(camera, "toggle")
    assert camera["_status"] == "on"
    assert call(camera, "get_power_consumption") == 10


def test_record_video():
    """测试摄像头的录制功能。"""
    clear_devices()
    camera = make(Camera, "大门摄像头", "玄关", 10, "on", 5)

    result = call(camera, "record_video", duration=30)
    assert result is not None
    assert "30" in result


# ==================== 测试场景 3: 管理接口功能 ====================
def test_management_interface():
    """测试 SmartHouse 管理接口的各项功能。"""
    clear_devices()

    make(Light, "书房灯", "书房", 40, "on", 80)
    make(Thermostat, "客厅温控", "客厅", 800, "on", 23, 21)
    make(Camera, "门禁", "玄关", 8, "on", 4)

    manager = create_SmartHouseManagement("测试系统")

    total_power = call(manager, "calculate_total_power_consumption")
    assert total_power > 0

    descriptions = call(manager, "get_all_device_description")
    assert len(descriptions) == 3


# ==================== 测试脚本主入口 ====================
if __name__ == "__main__":
    print("=== 智能家居系统单元测试 ===\n")

    tests = [
        test_device_creation,
        test_device_creation_invalid_input,
        test_light_functionality,
        test_thermostat_functionality,
        test_camera_functionality,
        test_record_video,
        test_management_interface
    ]

    passed = 0
    for test in tests:
        if run_test(test):
            passed += 1

    print(f"\n=== 测试完成: {passed}/{len(tests)} 通过 ===")