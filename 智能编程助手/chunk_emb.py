#文档解析模块 - 支持PDF、TXT、MD、代码文件
"""
模块1：文档解析模块 - 支持PDF、TXT、MD、代码文件
"""
import os
#设置国内镜像源
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from typing import List, Dict
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
#文本切片模块
from langchain_text_splitters import RecursiveCharacterTextSplitter
#嵌入模型模块
from langchain_huggingface import HuggingFaceEmbeddings
#向量数据库模块
from langchain_chroma import Chroma

class DocumentProcessor:
    """文档处理器：解析、切片、向量化、入库"""
#初始化
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory

        print("正在初始化嵌入模型...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        print("正在初始化向量数据库...")
        self.vectorstore = Chroma(
            collection_name="project_knowledge",
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", " ", ""],
            keep_separator=True
        )
#加载文件
    def load_document(self, file_path: str) -> List:
        """根据文件扩展名选择合适的加载器"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif ext == '.md':
            loader = UnstructuredMarkdownLoader(file_path)
        elif ext in ['.py', '.java', '.js', '.txt']:
            loader = TextLoader(file_path, encoding='utf-8')
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

        return loader.load()
#处理文件
    def process_and_store(self, file_path: str, metadata: Dict = None):
        """
        完整的处理流程：加载 → 切片 → 向量化 → 存储
        """
        print(f"正在处理: {file_path}")

        try:
            documents = self.load_document(file_path)

            if metadata:
                for doc in documents:
                    doc.metadata.update(metadata)

            chunks = self.text_splitter.split_documents(documents)
            print(f"  切分为 {len(chunks)} 个片段")

            self.vectorstore.add_documents(chunks)

            # 新版本不需要手动 persist，自动保存
            print(f"成功存入: {file_path}")

            return len(chunks)
        except Exception as e:
            print(f"  处理失败: {str(e)}")
            raise
#测试
if __name__ == "__main__":
    processor = DocumentProcessor()

    test_files = [
        ("./docs/api_document.txt", {"category": "api_doc", "project": "my_project"}),
        ("./src/main.py", {"category": "source_code", "language": "python"}),
    ]

    for file_path, metadata in test_files:
        if os.path.exists(file_path):
            try:
                processor.process_and_store(file_path, metadata)
            except Exception as e:
                print(f"跳过文件 {file_path}: {e}")
        else:
            print(f"文件不存在，跳过: {file_path}")

    print("\n处理完成！")
