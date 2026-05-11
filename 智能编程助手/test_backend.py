import requests
import json

API_BASE = "http://localhost:8000"

print("=" * 60)
print("后端完整测试")
print("=" * 60)

# 1. 健康检查
print("\n[1/3] 健康检查...")
try:
    resp = requests.get(f"{API_BASE}/api/health", timeout=5)
    print(f"状态码: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"失败: {e}")
    exit(1)

# 2. 测试非流式对话
print("\n[2/3] 测试非流式对话...")
try:
    resp = requests.post(
        f"{API_BASE}/api/chat",
        json={"message": "你好，请介绍一下自己", "session_id": "test"},
        timeout=60
    )
    print(f"状态码: {resp.status_code}")
    result = resp.json()
    if result.get("success"):
        print(f"回答: {result['answer'][:200]}...")
        print(f"来源数: {len(result.get('sources', []))}")
    else:
        print(f"错误: {result.get('error')}")
except Exception as e:
    print(f"失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试流式对话
print("\n[3/3] 测试流式对话...")
try:
    resp = requests.post(
        f"{API_BASE}/api/chat/stream",
        json={"message": "你好", "session_id": "test"},
        stream=True,
        timeout=60
    )
    print(f"状态码: {resp.status_code}")

    full_text = ""
    for line in resp.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data = line_str[6:]
                if data == '[DONE]':
                    break
                try:
                    parsed = json.loads(data)
                    if 'delta' in parsed:
                        full_text += parsed['delta']
                    elif 'error' in parsed:
                        print(f"错误: {parsed['error']}")
                        break
                except:
                    pass

    print(f"完整回答: {full_text[:200]}...")
    print("✅ 流式对话测试成功！")
except Exception as e:
    print(f"失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
