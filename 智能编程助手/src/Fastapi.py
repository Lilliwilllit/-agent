#Fastapi
"""
集成各大功能为可调用的api，方便运行调用
"""
# backend_all_in_one.py
"""
模块4：FastAPI后端服务
通过导入其他模块实现完整功能
"""

import os
import sys
import json
import uuid
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入自定义模块
from chunk_emb import DocumentProcessor
from retriever import HybridRetriever
from rag_prompt import RAGEngine
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings as HFEmbeddings

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
load_dotenv()

# ========== 1. 配置 ==========
class Settings:
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    llm_model: str = "qwen-plus"
    chroma_persist_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")
    redis_host: str = "localhost"
    redis_port: int = 6379

settings = Settings()

# ========== 2. 数据模型 ==========
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

# ========== 3. 全局依赖 ==========
retriever = None
rag_engine = None
redis_client = None
vectorstore = None
embeddings = None
doc_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever, rag_engine, redis_client, vectorstore, embeddings, doc_processor
    
    print("=" * 60)
    print("正在启动智能编程助手API...")
    print("=" * 60)
    
    # 1. 加载嵌入模型
    print("\n[1/5] 加载嵌入模型...")
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'}
        )
        print("✅ 嵌入模型加载完成")
    except Exception as e:
        print(f"⚠️ HuggingFaceEmbeddings 加载失败，尝试备用方案: {e}")
        embeddings = HFEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'}
        )
        print("✅ 备用嵌入模型加载完成")

    # 2. 连接向量数据库
    print("\n[2/5] 连接向量数据库...")
    vectorstore = Chroma(
        collection_name="project_knowledge",
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir
    )
    print("✅ 向量数据库连接成功")

    # 3. 初始化混合检索器（从 retriever.py 导入）
    print("\n[3/5] 初始化混合检索器...")
    retriever = HybridRetriever(vectorstore, embeddings)
    print("✅ 混合检索器初始化完成")

    # 4. 初始化RAG引擎（从 rag_prompt.py 导入）
    print("\n[4/5] 初始化RAG引擎...")
    rag_engine = RAGEngine(retriever)
    print("✅ RAG引擎初始化完成")

    # 5. 初始化文档处理器（从 chunk_emb.py 导入）
    print("\n[5/5] 初始化文档处理器...")
    doc_processor = DocumentProcessor(persist_directory=settings.chroma_persist_dir)

    print("✅ 文档处理器初始化完成")

    # 6. 连接Redis
    try:
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True
        )
        redis_client.ping()
        print("✅ Redis连接成功")
    except Exception as e:
        print(f"⚠️ Redis连接失败: {e}，将使用内存存储")
        redis_client = None

    print("\n" + "=" * 60)
    print("🚀 系统启动完成！")
    print("=" * 60)
    
    yield
    
    # 关闭时清理资源
    if redis_client:
        redis_client.close()
    print("系统已关闭")

app = FastAPI(lifespan=lifespan, title="智能编程助手API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ========== 4. 路由 ==========
@app.post("/api/chat/stream")
async def stream_chat(request: ChatRequest):
    """流式聊天接口"""
    def generate():
        try:
            for event in rag_engine.chat_stream(request.message):
                if event["type"] == "delta":
                    yield f"data: {json.dumps({'delta': event['content']})}\n\n"
                elif event["type"] == "done":
                    yield f"data: {json.dumps({'sources': event['sources']})}\n\n"
                    yield "data: [DONE]\n\n"
                elif event["type"] == "error":
                    yield f"data: {json.dumps({'error': event['error']})}\n\n"
                    yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"流式对话异常: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """非流式聊天接口"""
    result = rag_engine.chat(request.message)
    
    if result["success"]:
        # 保存历史记录到Redis
        if redis_client and request.session_id:
            history_entry = {
                "role": "user",
                "content": request.message,
                "timestamp": str(uuid.uuid4())
            }
            redis_client.lpush(f"chat_history:{request.session_id}", json.dumps(history_entry))
            
            assistant_entry = {
                "role": "assistant",
                "content": result["answer"],
                "sources": result["sources"],
                "timestamp": str(uuid.uuid4())
            }
            redis_client.lpush(f"chat_history:{request.session_id}", json.dumps(assistant_entry))
        
        return result
    else:
        raise HTTPException(status_code=500, detail=result["error"])

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """文档上传处理接口"""
    try:
        # 创建临时目录
        temp_dir = "./temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存上传的文件
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 准备元数据
        metadata = {
            "source": file.filename,
            "upload_time": str(uuid.uuid4()),
            "category": "user_upload"
        }
        
        # 处理并存储文档（使用导入的 DocumentProcessor）
        chunk_count = doc_processor.process_and_store(file_path, metadata)
        
        # 删除临时文件
        os.remove(file_path)
        
        return {
            "status": "ok",
            "filename": file.filename,
            "chunk_count": chunk_count,
            "message": f"成功处理 {chunk_count} 个文档片段"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """获取会话历史"""
    if not redis_client:
        return {"messages": [], "warning": "Redis未连接，无法获取历史"}
    
    try:
        history = redis_client.lrange(f"chat_history:{session_id}", 0, -1)
        return {"messages": [json.loads(m) for m in history]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话历史"""
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis未连接")
    
    try:
        redis_client.delete(f"chat_history:{session_id}")
        return {"status": "ok", "message": "会话历史已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "components": {
            "vectorstore": "connected" if vectorstore else "disconnected",
            "retriever": "initialized" if retriever else "not initialized",
            "rag_engine": "ready" if rag_engine else "not ready",
            "redis": "connected" if redis_client else "disconnected"
        }
    }

# ========== 5. 启动入口 ==========
if __name__ == "__main__":
    import uvicorn
    print("\n🎯 启动 FastAPI 服务器...")
    print("📍 地址: http://0.0.0.0:8000")
    print("📚 API文档: http://0.0.0.0:8000/docs")
    print("\n按 Ctrl+C 停止服务器\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)