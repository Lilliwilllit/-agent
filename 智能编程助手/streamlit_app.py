import streamlit as st
import requests
import json
import sseclient
import uuid
from dotenv import load_dotenv
import os
import time

# 加载环境变量（可选，用于配置后端地址）
load_dotenv()

# ---------- 后端地址 ----------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ---------- 页面配置 ----------
st.set_page_config(
    page_title="智能编程助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- 初始化 session 状态 ----------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = set()

# ---------- 侧边栏：知识库管理 ----------
with st.sidebar:
    st.title("📚 知识库管理")
    st.caption(f"会话ID: {st.session_state.session_id[:8]}...")

    # 文档上传
    st.subheader("上传文档")
    uploaded_file = st.file_uploader(
        "支持 PDF, Markdown, Python, TXT",
        type=["pdf", "md", "txt", "py"],
        key="file_uploader"
    )
    if uploaded_file is not None:
        if uploaded_file.name not in st.session_state.uploaded_files:
            with st.spinner(f"正在上传 {uploaded_file.name} ..."):
                files = {"file": uploaded_file}
                data = {"category": "user_upload"}
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/documents/upload",
                        files=files,
                        data=data
                    )
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ {uploaded_file.name} 上传成功！切分为 {result.get('chunk_count', 0)} 个片段")
                        st.session_state.uploaded_files.add(uploaded_file.name)
                    else:
                        st.error(f"上传失败: {response.text}")
                except Exception as e:
                    st.error(f"连接后端失败: {e}")

    # 显示已上传文件
    if st.session_state.uploaded_files:
        st.subheader("已上传文档")
        for fname in st.session_state.uploaded_files:
            st.write(f"📄 {fname}")

    st.divider()

    # 会话控制
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 新对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()
    with col2:
        if st.button("🗑️ 清空历史", use_container_width=True):
            try:
                requests.delete(f"{API_BASE_URL}/api/sessions/{st.session_state.session_id}")
                st.success("历史已清空")
                st.session_state.messages = []
            except:
                st.error("清空失败")

# ---------- 主界面：聊天区域 ----------
st.title("🤖 智能编程助手")
st.markdown("基于 RAG 技术的代码问答系统 — 答案均来自你的项目文档")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("📖 查看引用来源"):
                for src in msg["sources"]:
                    st.markdown(f"**文件：** `{src.get('file', 'unknown')}`")
                    st.markdown(f"**相关度：** {src.get('score', 0):.3f}")
                    st.markdown(f"**片段预览：** {src.get('content', '')[:200]}...")
                    st.divider()

# 输入框
if prompt := st.chat_input("问点什么？例如：数据库连接函数怎么用？"):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用后端流式接口
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        sources = None

        try:
            # 增加重试机制
            max_retries = 2
            retry_count = 0
            success = False
            
            while retry_count <= max_retries and not success:
                if retry_count > 0:
                    with st.spinner(f"重试中 ({retry_count}/{max_retries})..."):
                        time.sleep(1)
                
                try:
                    with requests.post(
                        f"{API_BASE_URL}/api/chat/stream",
                        json={
                            "message": prompt,
                            "session_id": st.session_state.session_id
                        },
                        stream=True,
                        timeout=60  # 增加到60秒
                    ) as response:
                        if response.status_code == 200:
                            client = sseclient.SSEClient(response)
                            for event in client.events():
                                if event.data == "[DONE]":
                                    break
                                try:
                                    data = json.loads(event.data)
                                    if "delta" in data:
                                        full_response += data["delta"]
                                        response_placeholder.markdown(full_response + "▌")
                                    elif "sources" in data:
                                        sources = data["sources"]
                                except json.JSONDecodeError as je:
                                    st.warning(f"JSON解析警告: {je}")
                                    continue
                            
                            # 显示最终回答（去掉光标）
                            response_placeholder.markdown(full_response)
                            # 保存到 session
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": full_response,
                                "sources": sources
                            })
                            success = True
                        else:
                            error_msg = f"后端错误: {response.status_code}"
                            if retry_count < max_retries:
                                retry_count += 1
                                continue
                            response_placeholder.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": error_msg
                            })
                            success = True  # 不再重试
                
                except requests.exceptions.ConnectionError as ce:
                    if retry_count < max_retries:
                        retry_count += 1
                        st.warning(f"连接失败，准备重试... ({ce})")
                        continue
                    else:
                        error_msg = f"连接后端失败，请检查后端服务是否启动: {ce}"
                        response_placeholder.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })
                        success = True
                        
                except requests.exceptions.Timeout as te:
                    if retry_count < max_retries:
                        retry_count += 1
                        st.warning(f"请求超时，准备重试... ({te})")
                        continue
                    else:
                        error_msg = f"请求超时（60秒），请稍后重试或简化问题: {te}"
                        response_placeholder.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })
                        success = True
                        
                except Exception as e:
                    error_msg = f"发生未知错误: {e}"
                    response_placeholder.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    success = True
                    
                retry_count += 1
                
        except Exception as e:
            error_msg = f"连接后端失败: {e}"
            response_placeholder.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg
            })

    st.rerun()