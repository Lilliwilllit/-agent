# rag_engine.py
#context上下文
"""
模块3：RAG引擎 + Prompt工程
"""
import os
from typing import List, Dict, Generator
from openai import OpenAI
from dotenv import load_dotenv
#设置镜像源
"""
模块3：rag和prompt提示词工程
实现：rag引擎和prompt提示词
输入：用户问题 + 模块2返回的片段
返回：最终答案（文本）+ 引用来源
"""
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
load_dotenv()
class RAGEngine:
    """RAG引擎 - 检索增强生成"""

    def __init__(self, retriever):
        self.retriever = retriever

        # 初始化通义千问客户端
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 默认模型
        self.model = "qwen-plus"

    def build_prompt(self, query: str, contexts: List[Dict]) -> str:
        """
        构建增强Prompt
        """
        # 构建上下文部分
        context_parts = []
        for i, ctx in enumerate(contexts, 1):
            source = ctx['metadata'].get('source', '未知来源')
            content = ctx['content']
            context_parts.append(f"【来源{i}：{source}】\n{content}")

        context_text = "\n\n---\n\n".join(context_parts)

        prompt = f"""你是一名资深软件工程师，正在帮助用户解决编程问题。

## 重要规则
1. 请严格基于以下【检索到的知识】来回答问题
2. 如果【检索到的知识】中没有相关信息，请明确告知"根据当前知识库，无法确定"
3. 不得编造或臆想知识库中不存在的信息
4. 在答案末尾标注引用来源

## 检索到的知识
{context_text}

## 用户问题
{query}

## 回答要求
- 使用中文回答
- 如果涉及代码，使用``语言```格式的代码块摘要	Ⅰ
Abstract	Ⅱ
1 引言	1
2. 相关工作与技术综述	2
2.1 大型语言模型在编程中的应用	2
2.2 检索增强生成技术原理	2
2.3 向量数据库技术选型分析	2
- 引用格式：[文件名]
- 回答要简洁、准确、有帮助

请回答："""

        return prompt

    def chat(self, query: str, top_k: int = 3) -> Dict:
        """
        非流式对话（一次性返回完整答案）
        """
        # 1. 检索相关上下文
        contexts = self.retriever.retrieve(query, top_k=top_k)

        # 2. 构建Prompt
        prompt = self.build_prompt(query, contexts)

        # 3. 提取来源信息
        sources = [
            {
                "file": ctx['metadata'].get('source', 'unknown'),
                "content": ctx['content'][:200],
                "score": ctx.get('rerank_score', 0)
            }
            for ctx in contexts
        ]

        # 4. 调用LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的编程助手，严格基于提供的上下文回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1024
            )

            answer = response.choices[0].message.content

            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "contexts_used": len(contexts)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sources": []
            }

    def chat_stream(self, query: str, top_k: int = 3) -> Generator:
        """
        流式对话（逐字返回）
        """
        try:
            # 1. 检索相关上下文
            contexts = self.retriever.retrieve(query, top_k=top_k)

            # 2. 构建Prompt
            prompt = self.build_prompt(query, contexts)

            # 3. 提取来源信息
            sources = [
                {
                    "file": ctx['metadata'].get('source', 'unknown'),
                    "content": ctx['content'][:200],
                    "score": ctx.get('rerank_score', 0)
                }
                for ctx in contexts
            ]

            # 4. 流式调用LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的编程助手，严格基于提供的上下文回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.3
            )

            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield {
                        "type": "delta",
                        "content": content,
                        "sources": sources if not full_response else None
                    }

            yield {
                "type": "done",
                "full_response": full_response,
                "sources": sources
            }

        except Exception as e:
            print(f"RAG引擎异常: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "error",
                "error": str(e)
            }


# 测试代码
if __name__ == "__main__":
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    print("=" * 60)
    print("模块3测试：RAG引擎")
    print("=" * 60)

    # 1. 连接向量数据库
    print("\n[1/3] 连接向量数据库...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={'device': 'cpu'}
    )
    vectorstore = Chroma(
        collection_name="project_knowledge",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )

    # 2. 初始化检索器和RAG引擎
    from retriever import HybridRetriever
    retriever = HybridRetriever(vectorstore, embeddings)
    rag = RAGEngine(retriever)

    # 3. 测试
    test_queries = [
        "数据库连接函数怎么用？",
        "如何查询用户信息？"
    ]
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"用户: {query}")
        print("-" * 50)

        result = rag.chat(query)

        if result["success"]:
            print(f"助手: {result['answer']}")
            print(f"\n📖 引用来源 ({len(result['sources'])}个):")
            for src in result['sources']:
                print(f"  - {src['file']} (相关度: {src['score']:.3f})")
        else:
            print(f"❌ 错误: {result['error']}")

    print("\n" + "=" * 60)
    print("✅ 模块3测试完成")