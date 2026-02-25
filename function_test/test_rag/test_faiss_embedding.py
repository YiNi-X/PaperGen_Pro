import os
import sys
import json
import logging
from dotenv import load_dotenv

# 确保能找到根目录的 config 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# LangChain 相关实体
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_rag_pipeline():
    load_dotenv()
    
    # 模拟从缓存文件读取已解析的长 PDF 文本
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")
    
    # 找寻最近的一个 ocr_cache 文件
    cache_files = [f for f in os.listdir(cache_dir) if f.startswith("ocr_cache_") and f.endswith(".json")]
    if not cache_files:
        logging.error("未找到任何 ocr_cache 文件进行测试。请先运行一次应用以上传 PDF。")
        return
        
    cache_file = os.path.join(cache_dir, cache_files[0])
    logging.info(f"读取样本文件: {cache_file}")
    
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
        
    pdf_text = cache_data.get("text", "")
    logging.info(f"原始文本长度: {len(pdf_text)} 字符")
    
    if len(pdf_text) < 100:
        logging.error("文本过短，难以测试 RAG 切片")
        return

    # 1. 文本切片
    logging.info("开始执行文本切片 (chunk_size=1000, overlap=200)...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    
    # 这里我们只存放文字，不携带复杂的 metadata，为了极致的上下文速度
    docs = text_splitter.create_documents([pdf_text])
    logging.info(f"切片完成，共计 {len(docs)} 个 Chunk。示例 Chunk 1 长度: {len(docs[0].page_content)}")

    # 2. 向量化与建立本地 FAISS 索引
    logging.info("加载本地 HuggingFace Embedding 模型 (BAAI/bge-small-zh-v1.5)...")
    # 使用 BGE small 模型，开源且对中英文检索特化，体积小速度快
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5"
    )
    
    try:
        logging.info("尝试组建 FAISS 向量数据库池...")
        vector_store = FAISS.from_documents(docs, embeddings)
        logging.info("FAISS 数据库建立成功！")
    except Exception as e:
        logging.error(f"Embeddings API 调用失败，请检查配置或提供支持 embedding 的 API 代理: {e}")
        return

    # 3. 模拟“撰写第 3 章”的 RAG 检索
    test_heading = "3.2 模型结构与算法实现"
    test_points = ["深度卷积网络的结构", "反向传播在特定任务的应用"]
    query = f"{test_heading} {' '.join(test_points)}"
    
    logging.info(f"\n=======================")
    logging.info(f"模拟 AI 写作查询 Query: {query}")
    
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})
    retrieved_docs = retriever.invoke(query)
    
    logging.info(f"检索到 {len(retrieved_docs)} 个高相关性文本块:")
    for i, d in enumerate(retrieved_docs):
        logging.info(f"\n[Chunk {i+1}] (长度: {len(d.page_content)})")
        logging.info(d.page_content[:200] + "......")
        
if __name__ == "__main__":
    try:
        test_rag_pipeline()
    except Exception as e:
        import traceback
        with open("function_test/test_rag/faiss_crash.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print("CRASH LOG WRITTEN TO faiss_crash.txt")
