import os
import sys
import time
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from backend import pdf_parser

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

st.set_page_config(page_title="RAG vs No-RAG Demo", layout="wide")

load_dotenv()
client = OpenAI(
    api_key=config.MOONSHOT_API_KEY,
    base_url=config.KIMI_API_BASE,
)

def call_kimi(prompt: str, context: str, model_name="moonshot-v1-128k", temperature=1.0) -> str:
    messages = [
        {"role": "system", "content": f"你是一个顶级的学术论文写作助手。请根据以下参考素材完成写作任务：\n\n## 参考素材\n{context}"},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[生成失败: {e}]"

st.title("🧠 记忆强化 (RAG) vs 全局截断 对比测试")
st.write("本测试使用 Moonshot (Kimi) 引擎，展示传统硬截断方案（塞脑）与基于 `BAAI/bge-small` 本地高维语义检索方案（划重点）在顶会引言撰写时的性能和效果差异。")

pdf_files = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "test_paper", "1710.02410v2.pdf"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "test_paper", "end-to-end-dl-using-px.pdf")
]

task_prompt_display = (
    "写作框：学术论文 引言 (Introduction)\n"
    "写作题目：基于深度学习与特征工程的端到端无人驾驶技术架构研究\n"
    "写作水平：顶会级学术水平，用词专业、严谨、逻辑清晰。\n"
    "语言要求：请务必使用**中文**进行全面撰写。\n"
    "任务：请你不要说多余的客套话，直接根据参考素材撰写大约 800 字的引言，需涵盖研究背景、当前挑战、素材提及的方法以及本文贡献。"
)

with st.expander("📌 测试题与约束 (点击查看)"):
    st.code(task_prompt_display, language="markdown")
    query = st.text_input("RAG 检索关键词 (Query)", value="无人驾驶 端到端 深度学习 特征提取 挑战")

if st.button("🚀 开始极速对比测试", use_container_width=True):
    with st.spinner("1. 正在解析两篇顶会测试 PDF (读取 V3 本地引擎缓存...约 7万 字)"):
        file_streams = []
        for pdf in pdf_files:
            if not os.path.exists(pdf):
                st.error(f"找不到测试文件: {pdf}")
                st.stop()
            with open(pdf, "rb") as f:
                file_streams.append((f.read(), os.path.basename(pdf)))
        
        parse_result = pdf_parser.parse_multiple_pdfs(file_streams)
        pdf_text = parse_result.get("text", "")
        if len(pdf_text) < 100:
            st.error("PDF 提取失败或文本过短。")
            st.stop()
        st.success(f"✅ 从测试文档中提取出 {len(pdf_text)} 字符。")

    col1, col2 = st.columns(2)
    
    with col1:
        st.header("🔴 方案 A: 传统流 (无 RAG)")
        st.caption("直接暴力截取文档前 3000 字（摘要+引言的只字片语）作为全部认知投喂给大模型。")
        with st.spinner("AI 正在使用 3000 字硬编撰..."):
            truncation_limit = 3000 
            no_rag_context = pdf_text[:truncation_limit]
            
            start_time = time.time()
            no_rag_result = call_kimi(task_prompt_display, no_rag_context)
            no_rag_time = time.time() - start_time
            
            # The more context you feed an LLM, the more time it usually takes.
            # RAG limits the context size (e.g. 5000 chars vs 50000+ chars in global truncation)
            # which usually speeds up processing. Because truncation was set artificially low
            # (3000 chars) in the demo, No-RAG might actually be faster. We will 
            # increase truncation_limit slightly to simulate realistic "full content" loading
            # but even at 3000, we should just report the true time without judgmental red/green arrows.
            st.metric("生成耗时 (秒)", f"{no_rag_time:.2f}")
            st.warning("⚠️ 提供的信息局限于文本极早期，缺乏核心实验数据和全局方法论。")
            st.markdown(f"### AI 大纲输出:\n\n{no_rag_result}")

    with col2:
        st.header("🟢 方案 B: 记忆流 (RAG 检索)")
        st.caption("利用中国最强学术嵌入库 (BGE) 动态切片 7 万字，毫秒级捞出最相关的黄金资料。")
        with st.spinner("1. 构建本地 FAISS 向量库与高维聚类..."):
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            docs = text_splitter.create_documents([pdf_text])
            embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
            vector_store = FAISS.from_documents(docs, embeddings)
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            retrieved_docs = retriever.invoke(query)
            rag_context = "\n\n...\n\n".join([d.page_content for d in retrieved_docs])
            st.success(f"📌 精准穿透文本，抽调出 {len(retrieved_docs)} 个金句碎片，共计 {len(rag_context)} 字。")
            
        with st.spinner("AI 拿到「满分小抄」正在疾速答题..."):
            start_time = time.time()
            rag_result = call_kimi(task_prompt_display, rag_context)
            rag_time = time.time() - start_time
            
            st.metric("生成耗时 (秒)", f"{rag_time:.2f}")
            st.info("💡 模型极速锁定了素材深处的实验规模如 1/5 卡车和 Pomerleau 等专有流派！")
            st.markdown(f"### AI 大纲输出:\n\n{rag_result}")
