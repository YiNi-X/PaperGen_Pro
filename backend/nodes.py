"""
PaperGen_Pro - LangGraph 节点定义 (V2)

每个节点是一个独立函数，接收 PaperState 并返回更新后的状态。
V2 新增：多文件解析、分章节写作、Word 编译节点。
"""
import hashlib
import json
import os
import re

from backend.state import PaperState
from backend import services
from backend import pdf_parser
from backend import doc_writer
import config

# RAG 相关 (Phase 3)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

# 全局缓存嵌入模型实例，避免每次调用都重新加载权重（约 100MB）
_embeddings_model = None

def _get_embeddings():
    """延迟加载并缓存 BGE 嵌入模型单例。"""
    global _embeddings_model
    if _embeddings_model is None:
        print("[RAG] 首次加载 BAAI/bge-small-zh-v1.5 嵌入模型...")
        _embeddings_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
        print("[RAG] 嵌入模型加载完成。")
    return _embeddings_model


def _build_vector_store(text: str, images_data: list = None):
    """
    将长文本切片并构建 FAISS 内存向量索引。
    如果提供了 images_data，会将每张图片的 rich_context 作为独立文档
    （带 metadata type=image）一并嵌入索引，实现按章节精准检索图片。
    
    Args:
        text: 完整的 PDF 解析文本。
        images_data: 图片信息列表（可选），包含 rich_context 字段。
        
    Returns:
        FAISS vector store 实例，或 None（如果文本过短/构建失败）。
    """
    if not text or len(text) < 200:
        print("[RAG] 文本过短，跳过向量库构建。")
        return None
    
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = splitter.create_documents([text])
        
        # 为每个纯文本 Chunk 打上 type=text 标签
        for doc in docs:
            doc.metadata["type"] = "text"
        
        print(f"[RAG] 文本切片完成: {len(docs)} 个 Chunk")
        
        # 将图片的富上下文作为独立文档嵌入
        img_doc_count = 0
        if images_data:
            for img in images_data:
                rich_ctx = img.get("rich_context", img.get("caption_context", ""))
                img_id = img.get("id", "")
                if rich_ctx and len(rich_ctx) > 10 and img_id:
                    img_doc = LCDocument(
                        page_content=rich_ctx,
                        metadata={"type": "image", "image_id": img_id}
                    )
                    docs.append(img_doc)
                    img_doc_count += 1
            print(f"[RAG] 图片文档嵌入: {img_doc_count} 张图片的上下文已加入向量库")
        
        embeddings = _get_embeddings()
        store = FAISS.from_documents(docs, embeddings)
        print(f"[RAG] FAISS 向量库构建成功 (共 {len(docs)} 个向量, 其中 {img_doc_count} 个为图片)")
        return store
    except Exception as e:
        print(f"[RAG] 向量库构建失败，将回退到传统截断模式: {e}")
        return None


def node_parse_pdf(state: PaperState) -> dict:
    """
    节点: 解析 PDF 文件 (V2 - 使用 PyMuPDF)。

    支持多文件解析、电子稿/扫描件自动判别、图片提取。
    """
    print("[Node] node_parse_pdf: 开始解析 PDF...")

    raw_files = state.get("_raw_files", [])

    if not raw_files:
        # 兼容：如果没有 _raw_files，尝试使用旧的 pdf_content
        print("[Node] node_parse_pdf: 未发现上传文件数据")
        return {
            "pdf_content": state.get("pdf_content", ""),
            "is_scanned": False,
            "images_data": [],
        }

    # 计算上传文件的哈希值，作为缓存键
    hasher = hashlib.md5()
    for stream, fname in raw_files:
        hasher.update(fname.encode("utf-8"))
        hasher.update(stream)
    cache_key = hasher.hexdigest()
    
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    cache_file = os.path.join(config.TEMP_DIR, f"ocr_cache_{cache_key}.json")

    # 尝试读取缓存，避免重复花费大量时间和金钱调用 OCR API
    if os.path.exists(cache_file):
        print(f"[Node] node_parse_pdf: 命中 OCR 本地缓存，直接加载 {cache_file}")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            
            # 兼容旧缓存：如果没有提取过参考文献，补齐
            refs_data = result.get("references_data")
            if refs_data is None:
                print(f"[Node] 旧缓存缺失参考文献数据，正在补齐提取...")
                refs_data = services.extract_references_from_text(result.get("text", ""))
                result["references_data"] = refs_data
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

            text = result.get("text", "")
            images = result.get("images_data", [])
            # 确保图片有 ID（缓存数据可能缺少）
            for i, img in enumerate(images):
                if "id" not in img:
                    img["id"] = f"img_{i:03d}"
            vector_store = _build_vector_store(text, images)
            return {
                "pdf_content": text,
                "is_scanned": result.get("is_scanned", True),
                "images_data": images,
                "references_data": result.get("references_data", []),
                "vector_store": vector_store,
            }
        except Exception as e:
            print(f"[Node] node_parse_pdf: 读取或更新缓存失败，将重新进行 OCR: {e}")

    # 使用多文件解析（带异常保护）
    try:
        result = pdf_parser.parse_multiple_pdfs(raw_files)
        
        # 提取参考文献
        refs_data = services.extract_references_from_text(result["text"])
        result["references_data"] = refs_data
        
        # 写入缓存
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[Node] node_parse_pdf: 解析结果已写入缓存 {cache_file}")
        except Exception as ce:
            print(f"[Node] node_parse_pdf: 缓存写入失败: {ce}")
            
    except Exception as e:
        print(f"[Node] node_parse_pdf: PDF 解析失败: {e}")
        return {
            "pdf_content": f"[错误] PDF 解析失败: {e}",
            "is_scanned": False,
            "images_data": [],
            "references_data": [],
        }

    text = result["text"]
    images = result["images_data"]
    # 确保图片有 ID
    for i, img in enumerate(images):
        if "id" not in img:
            img["id"] = f"img_{i:03d}"

    print(f"[Node] node_parse_pdf: 解析完成, "
          f"文本长度={len(text)}, "
          f"图片数={len(images)}, "
          f"含扫描件={result['is_scanned']}")

    vector_store = _build_vector_store(text, images)

    return {
        "pdf_content": text,
        "is_scanned": result["is_scanned"],
        "images_data": images,
        "references_data": result.get("references_data", []),
        "vector_store": vector_store,
    }


def node_generate_skeleton(state: PaperState) -> dict:
    """
    节点: 生成大纲骨架（仅章节标题）。

    基于解析后的 PDF 文本和用户意图，调用 DeepSeek 生成章节框架。
    """
    print("[Node] node_generate_skeleton: 开始生成大纲骨架...")

    pdf_text = state.get("pdf_content", "")
    user_intent = state.get("user_intent", "")

    # 构建论文配置
    paper_config = {
        "paper_subject": state.get("paper_subject", ""),
        "paper_title": state.get("paper_title", ""),
        "paper_language": state.get("paper_language", "中文"),
        "academic_type": state.get("academic_type", "本科"),
        "paper_level": state.get("paper_level", "初级"),
        "paper_type": state.get("paper_type", "毕业论文"),
        "target_word_count": state.get("target_word_count", 8000),
        "keywords_cn": state.get("keywords_cn", []),
        "keywords_en": state.get("keywords_en", []),
    }

    skeleton = services.call_deepseek_generate_skeleton(
        pdf_text=pdf_text,
        user_intent=user_intent,
        paper_config=paper_config,
    )

    print(f"[Node] node_generate_skeleton: 骨架生成完成, "
          f"包含 {len(skeleton.get('sections', []))} 个章节")
    return {"outline_skeleton": skeleton}


def node_generate_variants(state: PaperState) -> dict:
    """
    节点: 基于骨架生成两个对抗式大纲变体。

    变体 A: 严谨学术风格 (temperature=0.5)
    变体 B: 创新发散风格 (temperature=0.9)
    """
    print("[Node] node_generate_variants: 开始生成双变体大纲...")

    skeleton = state.get("outline_skeleton", {})
    pdf_text = state.get("pdf_content", "")
    user_intent = state.get("user_intent", "")

    paper_config = {
        "paper_subject": state.get("paper_subject", ""),
        "paper_title": state.get("paper_title", ""),
        "paper_language": state.get("paper_language", "中文"),
        "academic_type": state.get("academic_type", "本科"),
        "paper_level": state.get("paper_level", "初级"),
        "paper_type": state.get("paper_type", "毕业论文"),
        "target_word_count": state.get("target_word_count", 8000),
        "keywords_cn": state.get("keywords_cn", []),
        "keywords_en": state.get("keywords_en", []),
    }

    variant_a = services.call_deepseek_fill_variant_a(
        skeleton=skeleton,
        pdf_text=pdf_text,
        user_intent=user_intent,
        paper_config=paper_config,
    )

    variant_b = services.call_deepseek_fill_variant_b(
        skeleton=skeleton,
        pdf_text=pdf_text,
        user_intent=user_intent,
        paper_config=paper_config,
    )

    print(f"[Node] node_generate_variants: 双变体生成完成, "
          f"A={len(variant_a.get('sections', []))} 章, "
          f"B={len(variant_b.get('sections', []))} 章")
    return {
        "outline_variant_a": variant_a,
        "outline_variant_b": variant_b,
    }


def node_review_outline(state: PaperState) -> dict:
    """
    节点: 审阅并优化大纲。

    调用 DeepSeek 对生成的大纲进行审阅，返回修改建议。
    """
    print("[Node] node_review_outline: 开始审阅大纲...")

    outline = state.get("outline", {})
    feedback = services.call_deepseek_review_outline(outline=outline)

    print("[Node] node_review_outline: 审阅完成")
    return {"review_feedback": feedback}


def node_write_chapter(state: PaperState) -> dict:
    """
    节点: 分章节写作 (V2 新增)。

    遍历大纲中的每个章节，逐一调用 DeepSeek 生成正文内容。
    """
    print("[Node] node_write_chapter: 开始分章节写作...")

    outline = state.get("outline", {})
    pdf_context = state.get("pdf_content", "")
    vector_store = state.get("vector_store", None)
    images_data = state.get("images_data", [])
    references_data = state.get("references_data", [])
    sections = outline.get("sections", [])
    sections_content = {}

    # 给图片打上唯一 ID 放入状态，方便 AI 引用和后端组装
    for i, img in enumerate(images_data):
        if "id" not in img:
            img["id"] = f"img_{i:03d}"
            
    # 动态消费池：未被使用的图片
    available_images_pool = list(images_data)
    
    # 动态消费池：未被使用的参考文献
    available_references_pool = list(references_data)
    # 记录并排序已被使用的参考文献（用于文后按顺序生成 [1], [2]...）
    used_references = []

    for idx, section in enumerate(sections):
        heading = section.get("heading", f"第 {idx + 1} 章")
        points = section.get("points", [])

        print(f"[Node] node_write_chapter: 撰写第 {idx + 1}/{len(sections)} "
              f"章: {heading} (当前可用图片: {len(available_images_pool)} 张, 可用文献: {len(available_references_pool)} 篇)")

        # RAG 精准检索：只给 AI 看当前章节最相关的图片（而非全局硬塞）
        chapter_images = services._get_chapter_images(
            heading=heading,
            points=points,
            vector_store=vector_store,
            all_images=available_images_pool,
            k=3,
        )

        content = services.call_deepseek_write_chapter(
            heading=heading,
            points=points,
            context=pdf_context,
            full_outline=outline,
            images_data=chapter_images,
            references_data=available_references_pool,
            vector_store=vector_store,
            paper_config={
                "paper_language": state.get("paper_language", "中文"),
                "academic_type": state.get("academic_type", "本科"),
                "paper_level": state.get("paper_level", "初级"),
                "target_word_count": state.get("target_word_count", 8000),
            },
        )
        sections_content[heading] = content
        
        # 解析刚刚生成的本章内容，找出被 AI 用到的图片 ID
        used_img_ids = re.findall(r'\[INSERT_IMG_([^\]]+)\]', content)
        if used_img_ids:
            print(f"[Node] node_write_chapter: 本章使用了图片: {used_img_ids}")
            # 从全局缓冲池中剔除这些已被征用的图片，防止后续章节重复使用
            available_images_pool = [
                img for img in available_images_pool 
                if img["id"] not in used_img_ids
            ]

        # 解析被 AI 引用的参考文献 ID
        used_ref_ids = re.findall(r'\[REF_([^\]]+)\]', content)
        if used_ref_ids:
            print(f"[Node] node_write_chapter: 本章引用了文献: {used_ref_ids}")
            for ref_id in used_ref_ids:
                # 找到这篇文献的详情
                ref_item = next((r for r in available_references_pool if r["id"] == ref_id), None)
                if ref_item and ref_item not in used_references:
                    used_references.append(ref_item)
            
            # 注释旧逻辑：不要从可用文献池中剔除，因为不同章节可能引用同一篇文献
            # 只有图片为了防止重复插入才需要剔除

    print(f"[Node] node_write_chapter: 全部 {len(sections)} 章撰写完成")
    return {
        "sections_content": sections_content,
        "used_references": used_references
    }


def node_compile_word(state: PaperState) -> dict:
    """
    节点: 编译 Word 文档 (V2 新增)。

    将大纲、章节正文、图片组装为 Word 文档。
    """
    print("[Node] node_compile_word: 开始编译 Word 文档...")

    outline = state.get("outline", {})
    sections_content = state.get("sections_content", {})
    images_data = state.get("images_data", [])
    used_references = state.get("used_references", [])

    output_path = doc_writer.generate_docx(
        outline=outline,
        sections_content=sections_content,
        images_data=images_data,
        used_references=used_references,
    )

    print(f"[Node] node_compile_word: Word 文档编译完成: {output_path}")
    return {"final_doc_path": output_path}
