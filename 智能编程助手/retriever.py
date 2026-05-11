# retriever.py
"""
模块2：混合检索器 + 重排序
实现：向量检索 + BM25关键词检索 + RRF融合 + BGE重排序
返回：不是答案，是排序后的文档片段列表（含内容、元数据、分数）
"""
import os
#设置国内镜像源
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import numpy as np
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


class HybridRetriever:
    """混合检索器 - 向量检索 + BM25 + 重排序"""

    def __init__(self, vectorstore: Chroma, embeddings: HuggingFaceEmbeddings):
        self.vectorstore = vectorstore
        self.embeddings = embeddings

        # 初始化重排序模型（BGE-reranker）
        print("正在加载重排序模型...")
        self.reranker = CrossEncoder('BAAI/bge-reranker-base')
        print("✅ 重排序模型加载完成")

        # BM25相关
        self.documents = []      # 存储所有文档内容
        self.bm25 = None         # BM25索引
        self.is_bm25_ready = False

    def build_bm25_index(self, all_chunks: List[str]):
        """构建BM25关键词索引"""
        print(f"正在构建BM25索引，共 {len(all_chunks)} 个文档片段...")
        tokenized_docs = [doc.split() for doc in all_chunks]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.documents = all_chunks
        self.is_bm25_ready = True
        print("✅ BM25索引构建完成")

    def semantic_search(self, query: str, k: int = 5) -> List[Tuple]:
        """向量语义检索"""
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        return results

    def keyword_search(self, query: str, k: int = 3) -> List[Tuple[str, float]]:
        """BM25关键词检索"""
        if not self.is_bm25_ready:
            return []

        tokenized_query = query.split()
        scores = self.bm25.get_scores(tokenized_query)

        # 获取top-k
        top_indices = np.argsort(scores)[-k:][::-1]
        results = [(self.documents[i], scores[i]) for i in top_indices if scores[i] > 0]
        return results

    def reciprocal_rank_fusion(self,
                                semantic_results: List[Tuple],
                                keyword_results: List[Tuple],
                                k: int = 60) -> Dict[str, float]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法
        比简单加权平均更鲁棒
        """
        scores = {}

        # 语义检索结果
        for rank, (doc, score) in enumerate(semantic_results):
            doc_id = doc.page_content[:200]  # 用前200字符作为唯一标识
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            scores[f"{doc_id}_meta"] = doc

        # 关键词检索结果
        for rank, (doc_content, score) in enumerate(keyword_results):
            doc_id = doc_content[:200]
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        return scores

    def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        混合检索：语义检索 + 关键词检索 + RRF融合
        """
        # 1. 执行两种检索
        semantic_results = self.semantic_search(query, k=top_k)
        keyword_results = self.keyword_search(query, k=top_k)

        # 2. RRF融合
        fused_scores = self.reciprocal_rank_fusion(semantic_results, keyword_results)

        # 3. 提取结果
        results = []
        doc_ids = [id for id in fused_scores.keys() if not id.endswith("_meta")]

        for doc_id in doc_ids[:top_k]:
            doc = fused_scores.get(f"{doc_id}_meta")
            if doc:
                results.append({
                    "document": doc,
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "fusion_score": fused_scores[doc_id]
                })

        return results

    def rerank(self, query: str, candidates: List[Dict], top_n: int = 3) -> List[Dict]:
        """
        使用CrossEncoder进行重排序
        """
        if not candidates:
            return []

        # 准备输入对 (query, document)
        pairs = [(query, cand["content"]) for cand in candidates]

        # 计算相关性分数
        scores = self.reranker.predict(pairs)

        # 添加重排序分数
        for cand, score in zip(candidates, scores):
            cand["rerank_score"] = float(score)

        # 按重排序分数排序
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_n]

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        完整检索流程：混合检索 → 重排序
        """
        # 1. 混合检索获取候选（取更多候选供重排序）
        candidates = self.hybrid_search(query, top_k=5)

        # 2. 重排序精选
        final_results = self.rerank(query, candidates, top_n=top_k)

        return final_results

# 测试代码
if __name__ == "__main__":
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    print("=" * 60)
    print("模块2测试：混合检索与重排序")
    print("=" * 60)

    # 1. 连接已有的向量数据库
    print("\n[1/4] 连接向量数据库...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={'device': 'cpu'}
    )
    vectorstore = Chroma(
        collection_name="project_knowledge",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )
    print("✅ 向量数据库连接成功")

    # 2. 初始化混合检索器
    print("\n[2/4] 初始化混合检索器...")
    retriever = HybridRetriever(vectorstore, embeddings)

    # 3. 构建BM25索引（从向量库中提取所有文档）
    print("\n[3/4] 构建BM25索引...")
    # 注意：这里需要从vectorstore获取所有文档，实际使用中可能需要遍历
    # 简单起见，这里先跳过，实际使用时需要实现get_all_documents方法
    print("⚠️ 提示：BM25索引需要从向量库中获取所有文档")

    # 4. 测试检索
    print("\n[4/4] 测试检索...")
    test_queries = [
        "数据库连接",
        "如何查询用户",
        "API接口"
    ]

    for query in test_queries:
        print(f"\n🔍 查询: {query}")
        print("-" * 40)

        # 仅使用语义检索（对比用）
        semantic_results = vectorstore.similarity_search_with_score(query, k=2)
        print(f"语义检索结果数: {len(semantic_results)}")

        # 使用混合检索+重排序
        results = retriever.retrieve(query, top_k=2)
        print(f"混合检索+重排序结果数: {len(results)}")

        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] 重排序分数: {r.get('rerank_score', 'N/A'):.4f}")
            print(f"      来源: {r['metadata'].get('source', 'unknown')}")
            print(f"      内容: {r['content'][:100]}...")

    print("\n" + "=" * 60)
    print("✅ 模块2测试完成")