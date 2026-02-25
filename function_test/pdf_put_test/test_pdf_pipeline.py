"""
============================================================
PaperGen_Pro - PDF 处理管道可视化调试 (Streamlit 版 V3 最终版)
============================================================

管道步骤：
    Step 1: 加载 PDF + 元数据提取
    Step 2: 全页渲染为 PNG（含 thumbnail 预览）
    Step 3: 提取原生图片资产（保留原始无损插图）
    Step 4: 并行多模态 OCR（ThreadPoolExecutor + kimi-k2.5）
             → 每页输出完整 Markdown（含 LaTeX 公式/表格）
    Step 5: 文本清洗 + 公式统计
    Step 6: 文本分块

运行方式：
    streamlit run function_test/pdf_put_test/test_pdf_pipeline.py

依赖：
    pip install pymupdf streamlit Pillow openai python-dotenv
============================================================
"""

import os
import io
import re
import json
import base64
import tempfile
import threading
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz          # PyMuPDF
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st

# ── 加载 .env ──────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_ROOT, ".env"))

# ── 全局配置 ────────────────────────────────────────────────
CHUNK_SIZE              = 1000
SCANNED_TEXT_THRESHOLD  = 50
MIN_IMAGE_WIDTH         = 100
MIN_IMAGE_HEIGHT        = 100
CAPTION_CONTEXT_CHARS   = 300
API_BASE                = "https://api.moonshot.cn/v1"
OCR_MODEL               = "kimi-k2.5"
OCR_TEMPERATURE         = 1.0   # kimi-k2.5 only accepts T=1.0
DEFAULT_DPI             = 150   # matrix(2,2) → 144 dpi effective
DEFAULT_WORKERS         = 5

# OCR Prompt
_OCR_SYSTEM = (
    "你是一个专业的 PDF 解析器和排版还原助手。\n"
    "任务：精确识别提供的文档图片中的所有内容，并完整地还原为 Markdown 格式输出。\n"
    "要求：\n"
    "1. 纯文本内容保持原样的段落结构。\n"
    "2. 所有数学公式（行内或独立公式）使用 LaTeX 语法，包裹在 `$` 或 `$$` 中输出。\n"
    "3. 表格使用 Markdown 表格语法还原。\n"
    "4. 忽略页眉、页脚、无关页码，只输出正文、图表题注及公式。\n"
    "5. 不要输出任何多余的开头或结尾寒暄语，直接返回 Markdown 文本即可。"
)


# ============================================================
#  STEP 1: load_pdf
# ============================================================
def load_pdf(file_path: str, filename: str) -> Optional[Tuple]:
    """加载 PDF 并提取基础元数据。"""
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        st.error(f"❌ 无法打开 PDF：{e}")
        return None

    meta        = doc.metadata
    page_count  = len(doc)
    size_bytes  = os.path.getsize(file_path)
    size_kb     = size_bytes / 1024

    first_text  = doc[0].get_text("text").strip() if page_count > 0 else ""
    is_scanned  = len(first_text) < SCANNED_TEXT_THRESHOLD

    meta_report = {
        "filename"             : filename,
        "file_size_bytes"      : size_bytes,
        "file_size_kb"         : round(size_kb, 2),
        "page_count"           : page_count,
        "is_scanned_preview"   : is_scanned,
        "first_page_char_count": len(first_text),
        "metadata"             : meta,
    }
    return doc, meta_report, is_scanned


# ============================================================
#  STEP 2: render_pages
# ============================================================
def render_pages(doc: fitz.Document, dpi: int = DEFAULT_DPI) -> List[Dict]:
    """
    渲染每页为 PNG 字节，附带缩略图。
    返回 [{"page": int, "img_bytes": bytes, "thumb": PIL.Image}]
    """
    scale  = dpi / 72.0   # 72 dpi 是 PyMuPDF 的基础 DPI
    matrix = fitz.Matrix(scale, scale)
    pages  = []
    for i in range(len(doc)):
        pix       = doc[i].get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        # 缩略图 (max 300px 宽)
        pil       = Image.open(io.BytesIO(img_bytes))
        thumb_w   = min(300, pil.width)
        thumb_h   = int(pil.height * thumb_w / pil.width)
        thumb     = pil.resize((thumb_w, thumb_h), Image.LANCZOS)
        pages.append({"page": i + 1, "img_bytes": img_bytes, "thumb": thumb})
    return pages


def _extract_caption_context(page: fitz.Page, image_bbox: fitz.Rect, context_chars: int = CAPTION_CONTEXT_CHARS) -> str:
    """提取图片周围的文本作为 caption 上下文"""
    try:
        page_text = page.get_text("text").strip()
        if not page_text:
            return ""
            
        words = page.get_text("words")
        if not words:
            return ""
            
        # 寻找距离图片 bbox 最近的词作为基准点
        min_dist = float('inf')
        closest_word_idx = -1
        
        for i, w in enumerate(words):
            w_rect = fitz.Rect(w[:4])
            
            # 计算单词矩形和图片矩形的中心点距离
            dx = max(0, w_rect.x0 - image_bbox.x1) + max(0, image_bbox.x0 - w_rect.x1)
            dy = max(0, w_rect.y0 - image_bbox.y1) + max(0, image_bbox.y0 - w_rect.y1)
            dist = (dx**2 + dy**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_word_idx = i
                
        if closest_word_idx == -1:
            return ""
            
        # 提取前后上下文
        start_idx = max(0, closest_word_idx - 50)  # 向前取约50个词
        end_idx = min(len(words), closest_word_idx + 50)  # 向后取约50个词
        
        context_words = words[start_idx:end_idx]
        context_text = " ".join([w[4] for w in context_words])
        
        # 截断到指定字符数
        if len(context_text) > context_chars * 2:
            center = len(context_text) // 2
            half = context_chars
            context_text = context_text[max(0, center-half):min(len(context_text), center+half)]
            
        return context_text.strip()
    except Exception as e:
        return f"[提取上下文失败: {str(e)}]"


# ============================================================
#  STEP 3: extract_images
# ============================================================
def extract_images_from_pdf(doc: fitz.Document, filename: str) -> List[Dict]:
    """提取页面中的原生无损图片资产及上下文。"""
    images_data = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                img_pil = Image.open(io.BytesIO(image_bytes))
                width, height = img_pil.width, img_pil.height
                
                if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                    continue
                
                # 获取图片在页面上的边界框以提取上下文
                image_rects = page.get_image_rects(xref)
                caption_context = ""
                if image_rects:
                    # 通常取第一个匹配的空间位置
                    caption_context = _extract_caption_context(page, image_rects[0], CAPTION_CONTEXT_CHARS)
                
                images_data.append({
                    "image_bytes": image_bytes,
                    "ext": image_ext,
                    "width": width,
                    "height": height,
                    "page": page_num + 1,
                    "img_index": img_idx + 1,
                    "caption_context": caption_context,
                    "source_file": filename,
                    "size_label": f"{width}×{height}",
                })
            except Exception:
                continue
                
    return images_data


# ============================================================
#  STEP 4: parallel_ocr
# ============================================================
def _ocr_one_page(page_info: Dict, api_key: str) -> Dict:
    """单页 OCR（在线程池中运行）。"""
    b64     = base64.b64encode(page_info["img_bytes"]).decode("utf-8")
    client  = OpenAI(api_key=api_key, base_url=API_BASE)
    try:
        resp = client.chat.completions.create(
            model       = OCR_MODEL,
            temperature = OCR_TEMPERATURE,
            messages    = [
                {"role": "system", "content": _OCR_SYSTEM},
                {"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text",
                     "text": "请将该页面转换为带公式的 Markdown。"},
                ]},
            ],
        )
        md = resp.choices[0].message.content.strip()
        return {"page": page_info["page"], "markdown": md, "error": None}
    except Exception as e:
        return {"page": page_info["page"], "markdown": "", "error": str(e)}


def parallel_ocr(
    pages: List[Dict],
    api_key: str,
    max_workers: int = DEFAULT_WORKERS,
) -> List[Dict]:
    """并行调用 OCR API。返回按页码排序的结果列表。"""
    total   = len(pages)
    results = [None] * total
    lock    = threading.Lock()

    progress_bar   = st.progress(0, text="⏳ 并行 OCR 进行中...")
    status_area    = st.empty()
    done_count     = [0]

    page_cols = st.columns(min(3, total))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_ocr_one_page, p, api_key): i
            for i, p in enumerate(pages)
        }

        for future in as_completed(future_to_idx):
            idx    = future_to_idx[future]
            result = future.result()
            results[idx] = result

            with lock:
                done_count[0] += 1
                done = done_count[0]

            progress_bar.progress(done / total, text=f"⏳ 已完成 {done}/{total} 页…")

            col_idx = (result["page"] - 1) % len(page_cols)
            with page_cols[col_idx]:
                if result["error"]:
                    st.error(f"第 {result['page']} 页 ❌ {result['error'][:60]}")
                else:
                    st.caption(f"✅ 第 {result['page']} 页")
                    preview = result["markdown"][:300].replace("\n", " ")
                    st.code(preview, language=None)

    progress_bar.progress(1.0, text="✅ 全部页面 OCR 完成！")
    status_area.empty()
    return results


# ============================================================
#  STEP 5: clean_text
# ============================================================
def clean_text(raw: str) -> Tuple[str, Dict]:
    original_len = len(raw)
    cleaned = raw

    cleaned = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufeff\u200b\u200c\u200d\ufff0-\uffff]",
        "", cleaned
    )
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    cleaned = cleaned.strip()

    cleaned_len = len(cleaned)
    reduction   = original_len - cleaned_len

    block_formula_count  = len(re.findall(r"\$\$[\s\S]+?\$\$", cleaned))
    inline_formula_count = len(re.findall(r"(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)", cleaned))

    stats = {
        "original_chars"      : original_len,
        "cleaned_chars"       : cleaned_len,
        "reduced_chars"       : reduction,
        "compression_rate"    : f"{reduction / max(original_len, 1) * 100:.1f}%",
        "block_formulas"      : block_formula_count,
        "inline_formulas"     : inline_formula_count,
    }
    return cleaned, stats


# ============================================================
#  STEP 6: chunk_text
# ============================================================
def chunk_text(cleaned_text: str, chunk_size: int = CHUNK_SIZE) -> Tuple[List[Dict], int]:
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
    chunks, buf, buf_len = [], [], 0

    for para in paragraphs:
        pl = len(para)
        if pl > chunk_size:
            if buf:
                content = "\n\n".join(buf)
                chunks.append({"index": len(chunks) + 1, "char_count": len(content), "content": content})
                buf, buf_len = [], 0
            for i in range(0, pl, chunk_size):
                sub = para[i:i + chunk_size]
                chunks.append({"index": len(chunks) + 1, "char_count": len(sub), "content": sub})
        elif buf_len + pl > chunk_size:
            content = "\n\n".join(buf)
            chunks.append({"index": len(chunks) + 1, "char_count": len(content), "content": content})
            buf, buf_len = [para], pl
        else:
            buf.append(para)
            buf_len += pl

    if buf:
        content = "\n\n".join(buf)
        chunks.append({"index": len(chunks) + 1, "char_count": len(content), "content": content})

    return chunks, len(paragraphs)


# ============================================================
#  Streamlit 主界面
# ============================================================
def main():
    st.set_page_config(
        page_title="PDF 多模态管道 (完全体 V3)",
        page_icon="🧠",
        layout="wide",
    )

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    h1 { font-family: 'Inter', sans-serif; }
    .step-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid rgba(148,163,184,.15);
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1rem;
    }
    .step-title {
        font-size: 1.1rem; font-weight: 700; color: #e2e8f0;
    }
    .badge {
        display:inline-block; border-radius:999px;
        font-size:.78rem; font-weight:600; padding:.18rem .65rem;
        margin-left:.4rem;
    }
    .badge-ocr  { background:#6366f1; color:#fff; }
    .badge-ok   { background:#22c55e; color:#fff; }
    .badge-warn { background:#f59e0b; color:#1a1a2e; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## ⚙️ 配置")
        api_key = st.text_input(
            "Moonshot API Key",
            value=os.environ.get("MOONSHOT_API_KEY", ""),
            type="password",
        )
        render_dpi = st.select_slider(
            "渲染 DPI",
            options=[72, 100, 150, 200, 300],
            value=150,
        )
        max_workers = st.slider("最大并发数", min_value=1, max_value=10, value=5)

    st.markdown("# 🧠 PDF 多模态 OCR 管道 · 完全体 V3")
    st.caption("全页渲染 → 原生无损图片抓取 → 并行多模态 AI 识别")

    uploaded = st.file_uploader("选择 PDF 文件", type=["pdf"])
    if not uploaded:
        st.info("👆 请先上传一个 PDF 文件以启动管道。")
        return

    if not api_key:
        st.error("❌ 缺少 API Key。")
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name

    # ============== STEP 1 ==============
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">✅ STEP 1 — 加载 PDF<span class="badge badge-ok">load_pdf</span></div></div>', unsafe_allow_html=True)

    result = load_pdf(tmp_path, uploaded.name)
    if not result: return
    doc, meta_report, is_scanned = result

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📄 文件名", uploaded.name[:20])
    c2.metric("📏 大小", f"{meta_report['file_size_kb']:.1f} KB")
    c3.metric("📑 总页数", meta_report['page_count'])
    c4.metric("🔤 首页字符", meta_report['first_page_char_count'])

    # ============== STEP 2 ==============
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">🖼️ STEP 2 — 全页渲染<span class="badge badge-ocr">render_pages</span></div></div>', unsafe_allow_html=True)

    with st.spinner(f"正在以 {render_dpi} DPI 渲染 {meta_report['page_count']} 页…"):
        pages = render_pages(doc, dpi=render_dpi)
    st.success(f"✅ 渲染完成，共 {len(pages)} 张图片。")

    # ============== STEP 3 ==============
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">📸 STEP 3 — 提取原生保留插图<span class="badge badge-ok">extract_images</span></div></div>', unsafe_allow_html=True)
    
    with st.spinner("正在从 PDF 结构中深层提取原始插入位图…"):
        images_data = extract_images_from_pdf(doc, uploaded.name)
        
    # Now we can safely close doc
    doc.close()

    st.success(f"✅ 提取完成。成功获取到 {len(images_data)} 张有效原生图片。")
    if images_data:
        with st.expander(f"✨ 原生图片画廊（{len(images_data)} 张）", expanded=False):
            img_cols = st.columns(min(3, len(images_data)))
            for i, img_dict in enumerate(images_data):
                with img_cols[i % 3]:
                    st.image(img_dict["image_bytes"], use_container_width=True)
                    st.caption(f"第 {img_dict['page']} 页 · {img_dict['size_label']} · .{img_dict['ext']}")
                    if img_dict.get("caption_context"):
                        with st.expander("📝 查看 Caption 上下文", expanded=False):
                            st.write(img_dict["caption_context"])

    # ============== STEP 4 ==============
    st.markdown("---")
    st.markdown(f'<div class="step-card"><div class="step-title">🤖 STEP 4 — 并行多模态 OCR<span class="badge badge-ocr">{max_workers} 并发</span></div></div>', unsafe_allow_html=True)

    ocr_results = parallel_ocr(pages, api_key=api_key, max_workers=max_workers)

    success_count = sum(1 for r in ocr_results if not r["error"])
    combined_md = "\n\n---\n\n".join(
        f"<!-- Page {r['page']} -->\n{r['markdown']}" if r['markdown'] else f"<!-- Page {r['page']} ERROR: {r['error']} -->"
        for r in ocr_results
    )

    with st.expander("📄 逐页 OCR 结果浏览", expanded=False):
        for r in ocr_results:
            hdr = f"第 {r['page']} 页 {'✅' if not r['error'] else '❌'}"
            with st.expander(hdr, expanded=False):
                if r["error"]: st.error(r["error"])
                else: st.markdown(r["markdown"][:3000])

    # ============== STEP 5 ==============
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">🧹 STEP 5 — 文本清洗 + 公式统计<span class="badge badge-ok">clean_text</span></div></div>', unsafe_allow_html=True)

    cleaned, clean_stats = clean_text(combined_md)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("清洗后字符", f"{clean_stats['cleaned_chars']:,}")
    c2.metric("压缩率", clean_stats['compression_rate'])
    c3.metric("🔢 独立公式 $$", clean_stats['block_formulas'])
    c4.metric("📐 行内公式 $", clean_stats['inline_formulas'])

    # ============== STEP 6 ==============
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">✂️ STEP 6 — 文本分块<span class="badge badge-ok">chunk_text</span></div></div>', unsafe_allow_html=True)

    chunks, para_count = chunk_text(cleaned, chunk_size=CHUNK_SIZE)
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 自然段落", para_count)
    c2.metric("✂️ 切分块数", len(chunks))

    # ============== 汇总 ================
    st.markdown("---")
    st.markdown('<div class="step-card"><div class="step-title">🎉 全部步骤执行完毕 · 汇总</div></div>', unsafe_allow_html=True)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("📄 页数", f"{len(pages)}")
    s2.metric("📸 原生插图", f"{len(images_data)}")
    s3.metric("🔢 图表公式", f"{clean_stats['block_formulas']} 公式")
    s4.metric("✂️ 最终分块", len(chunks))

    # 下载区
    st.markdown("##### 📥 下载结果")
    dl1, dl2, dl3, dl4 = st.columns(4)
    dl1.download_button("Step 4 · OCR Markdown", data=combined_md, file_name="step4_ocr_result.md", mime="text/markdown")
    dl2.download_button("Step 5 · 清洗文本", data=cleaned, file_name="step5_cleaned.md", mime="text/markdown")
    if images_data:
        # 导出带 caption info 的图片 metadata json
        img_meta = [
            {k: v for k, v in d.items() if k != "image_bytes"}
            for d in images_data
        ]
        
        dl3.download_button(
            "Step 3 · 图片信息 (JSON)", 
            data=json.dumps(img_meta, ensure_ascii=False, indent=2), 
            file_name="step3_images_meta.json", mime="application/json"
        )
        dl4.download_button(
            "Step 3 · [示例] 首张截图", 
            data=images_data[0]["image_bytes"], 
            file_name=f"figure_p{images_data[0]['page']}.{images_data[0]['ext']}", 
            mime=f"image/{images_data[0]['ext']}"
        )

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

if __name__ == "__main__":
    main()
