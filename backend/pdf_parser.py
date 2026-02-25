"""
PaperGen_Pro - PDF 解析模块 (V3 最终版)

完整的双通道架构：
1. 提取原生无损插图并存盘（`ext`, `width`, `height`），带 `caption_context`。
2. 并行全局多模态 OCR（kimi-k2.5），将所有页面的文本、排版、表格、公式（LaTeX）完整还原为 Markdown。
"""

import os
import io
import re
import json
import base64
import threading
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
from PIL import Image
from openai import OpenAI

import config


def parse_pdf(file_stream: bytes, filename: str = "document.pdf") -> Dict:
    """
    解析 PDF 文件。V3 版本对所有文件进行：
      1. 全页渲染
      2. 提取原生图片
      3. 并行多线程多模态 OCR
      4. 轻度清洗

    Returns:
        dict: {
            "text": str,           # Markdown + LaTeX 整文
            "is_scanned": bool,    # V3 统一视为 true 让后续知道已 OCR
            "images_data": list,   # 原生图片列表（含本地存盘路径 path 和 caption_context）
        }
    """
    os.makedirs(config.TEMP_FIGURES_DIR, exist_ok=True)

    doc = fitz.open(stream=file_stream, filetype="pdf")
    page_count = len(doc)
    print(f"[PDF Parser V3] 打开文件: {filename}, 共 {page_count} 页")

    # Step 1: 扫描全页提取图片资产
    images_data = _extract_native_images(doc, filename)
    print(f"[PDF Parser V3] 提取到 {len(images_data)} 张原生图片")

    # Step 2: 全页渲染
    # matrix=2 相当于 144 DPI，平衡速度与精度
    matrix = fitz.Matrix(2, 2)
    pages_for_ocr = []
    
    print(f"[PDF Parser V3] 开始渲染 {page_count} 页用于 OCR...")
    for i in range(page_count):
        pix = doc[i].get_pixmap(matrix=matrix)
        pages_for_ocr.append({"page": i + 1, "img_bytes": pix.tobytes("png")})

    doc.close()

    # Step 3: 并发 OCR 调用
    print(f"[PDF Parser V3] 开始 {config.MAX_WORKERS if hasattr(config, 'MAX_WORKERS') else 5} 并发多模态 OCR...")
    ocr_results = _parallel_ocr_pages(pages_for_ocr)

    # 合并结果
    combined_md = "\n\n---\n\n".join(
        f"<!-- Page {r['page']} -->\n{r['markdown']}"
        if r['markdown'] else f"<!-- Page {r['page']} ERROR: {r['error']} -->"
        for r in ocr_results
    )

    # Step 4: 清洗文本
    final_text = _clean_text(combined_md)
    print(f"[PDF Parser V3] OCR 与清洗完成，最终文本长度: {len(final_text)}")

    # Step 5: 利用 OCR 全文为图片上下文做语义富化（零额外 API 调用）
    _enrich_image_contexts(images_data, final_text)

    return {
        "text": final_text,
        "is_scanned": True, # 对于下游流程统一，因为我们已经全部通过 OCR 和 Markdown 提取了
        "images_data": images_data,
    }


def parse_multiple_pdfs(file_streams: List[Tuple[bytes, str]]) -> Dict:
    """
    解析多个 PDF 文件，合并结果以供写作图谱调用。
    """
    all_text_parts = []
    all_images = []

    for idx, (stream, fname) in enumerate(file_streams):
        print(f"\n[PDF Parser V3] === 解析第 {idx + 1}/{len(file_streams)} 个文件: {fname} ===")
        result = parse_pdf(stream, fname)
        all_text_parts.append(f"\n\n{'='*60}\n📄 文件: {fname}\n{'='*60}\n\n{result['text']}")
        all_images.extend(result["images_data"])

    return {
        "text": "\n".join(all_text_parts),
        "is_scanned": True,
        "images_data": all_images,
    }


def _extract_native_images(doc: fitz.Document, filename: str) -> List[Dict]:
    """提取原生保留插图，并存放到临时目录。"""
    images_data = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")
                
                img_pil = Image.open(io.BytesIO(image_bytes))
                width, height = img_pil.width, img_pil.height
                
                if width < config.MIN_IMAGE_WIDTH or height < config.MIN_IMAGE_HEIGHT:
                    continue
                
                # 寻找上下文
                caption_context = ""
                image_rects = page.get_image_rects(xref)
                if image_rects:
                    raw_context = _extract_caption_context(page, image_rects[0], config.CAPTION_CONTEXT_CHARS)
                    # 清除原论文的图片标号 (例如 "Figure 1:", "图3(b) - ")，保留纯粹的图片名字+片段
                    # 匹配: 图/Figure/Fig. + 数字 + 可能的字母编号(如 1a, 1(a), 1（b）) + 可能的分隔符
                    pattern = r'(?:图|Figure|Fig\.?)\s*\d+(?:[a-zA-Z]|\([a-zA-Z]\)|（[a-zA-Z]）)*[\s:：\.\-]*'
                    caption_context = re.sub(pattern, '', raw_context, flags=re.IGNORECASE).strip()

                # 存入物理磁盘（供下游 doc_writer 使用）
                safe_name = filename.replace(" ", "_").replace(".", "_")
                img_filename = f"{safe_name}_page{page_num + 1}_img{img_idx + 1}.{image_ext}"
                img_path = os.path.join(config.TEMP_FIGURES_DIR, img_filename)

                with open(img_path, "wb") as f:
                    f.write(image_bytes)

                images_data.append({
                    "path": img_path,
                    "page": page_num + 1,
                    "caption_context": caption_context,
                    "source_file": filename,
                    "size": f"{width}x{height}",
                })
            except Exception as e:
                print(f"[PDF Parser V3] 提取图片异常 P{page_num+1}_{img_idx+1}: {e}")
                continue
                
    return images_data


def _extract_caption_context(page: fitz.Page, image_bbox: fitz.Rect, context_chars: int) -> str:
    """提取图片周围的文本作为 caption 上下文"""
    try:
        page_text = page.get_text("text").strip()
        if not page_text:
            return ""
            
        words = page.get_text("words")
        if not words:
            return ""
            
        min_dist = float('inf')
        closest_word_idx = -1
        
        for i, w in enumerate(words):
            w_rect = fitz.Rect(w[:4])
            dx = max(0, w_rect.x0 - image_bbox.x1) + max(0, image_bbox.x0 - w_rect.x1)
            dy = max(0, w_rect.y0 - image_bbox.y1) + max(0, image_bbox.y0 - w_rect.y1)
            dist = (dx**2 + dy**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_word_idx = i
                
        if closest_word_idx == -1:
            return ""
            
        start_idx = max(0, closest_word_idx - 50)
        end_idx = min(len(words), closest_word_idx + 50)
        
        context_words = words[start_idx:end_idx]
        context_text = " ".join([w[4] for w in context_words])
        
        if len(context_text) > context_chars * 2:
            center = len(context_text) // 2
            half = context_chars
            context_text = context_text[max(0, center-half):min(len(context_text), center+half)]
            
        return context_text.strip()
    except Exception:
        return ""


def _ocr_one_page(page_info: Dict) -> Dict:
    """内部单页 OCR 线程函数"""
    b64 = base64.b64encode(page_info["img_bytes"]).decode("utf-8")
    client = OpenAI(
        api_key=config.MULTIMODAL_API_KEY, 
        base_url=config.MULTIMODAL_API_BASE
    )
    
    # 获取需要使用的模型
    model_name = getattr(config, "MULTIMODAL_MODEL_NAME", "kimi-k2.5")
    # Kimi 要求 1.0，其他可以 0.1
    temp = 1.0 if "kimi" in model_name else 0.1
    
    system_prompt = (
        "你是一个专业的 PDF 解析器和排版还原助手。\n"
        "任务：精确识别提供的文档图片中的所有内容，并完整地还原为 Markdown 格式输出。\n"
        "要求：\n"
        "1. 纯文本内容保持原样的段落结构。\n"
        "2. 所有数学公式（行内或独立公式）使用 LaTeX 语法，包裹在 `$` 或 `$$` 中输出。\n"
        "3. 表格使用 Markdown 表格语法还原。\n"
        "4. 忽略页眉、页脚、无关页码，只输出正文、图表题注及公式。\n"
        "5. 不要输出任何多余的开头或结尾寒暄语，直接返回 Markdown 文本即可。"
    )
    
    try:
        resp = client.chat.completions.create(
            model=model_name,
            temperature=temp,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": "请精确识别该页面为 Markdown"},
                ]},
            ],
        )
        md = resp.choices[0].message.content.strip()
        return {"page": page_info["page"], "markdown": md, "error": None}
    except Exception as e:
        return {"page": page_info["page"], "markdown": "", "error": str(e)}


def _parallel_ocr_pages(pages_for_ocr: List[Dict]) -> List[Dict]:
    """多线程并发执行 OCR"""
    total = len(pages_for_ocr)
    results = [None] * total
    max_workers = getattr(config, "MAX_WORKERS", 5)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_ocr_one_page, p): i
            for i, p in enumerate(pages_for_ocr)
        }
        
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"page": pages_for_ocr[idx]["page"], "markdown": "", "error": str(e)}
            
            results[idx] = res
            done += 1
            if done % max_workers == 0 or done == total:
                print(f"[PDF Parser V3] 并发 OCR 进度: {done}/{total} 页")
                
    return results


def _clean_text(raw: str) -> str:
    """去噪清洗"""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufeff\u200b\u200c\u200d\ufff0-\uffff]", "", raw)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def _enrich_image_contexts(images_data: List[Dict], full_text: str) -> None:
    """
    利用已有的 OCR Markdown 全文，为每张图片的上下文做语义富化。
    
    原理：图片的短 caption_context (由物理距离抓取) 往往干瘪，
    但 OCR 全文中几乎一定包含了对该图片更详细的描述段落。
    我们用 caption 中的关键词做模糊锚点匹配，精准截取这段富文本。
    
    零额外 API 调用 —— 纯字符串操作，耗时 < 50ms。
    """
    if not images_data or not full_text:
        return
    
    # 将全文切成段落（按双换行分割），每个段落作为匹配候选
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', full_text) if p.strip() and len(p.strip()) > 20]
    
    if not paragraphs:
        print("[PDF Parser V3] 全文段落为空，跳过图片上下文富化")
        return
    
    enriched_count = 0
    
    for img in images_data:
        caption = img.get("caption_context", "")
        if not caption or len(caption) < 5:
            continue
        
        # 提取 caption 中的关键词（去掉常见停用词和短词）
        # 用中文按字符切和英文按空格切的混合方式
        keywords = set()
        for word in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', caption):
            keywords.add(word.lower())
        
        if not keywords:
            continue
        
        # 在全文段落中找"命中关键词最多"的段落
        best_para_idx = -1
        best_score = 0
        
        for pidx, para in enumerate(paragraphs):
            para_lower = para.lower()
            score = sum(1 for kw in keywords if kw in para_lower)
            if score > best_score:
                best_score = score
                best_para_idx = pidx
        
        if best_para_idx >= 0 and best_score >= 2:
            # 以最佳段落为中心，取前后1段，拼接成 ~500 字的富上下文
            start = max(0, best_para_idx - 1)
            end = min(len(paragraphs), best_para_idx + 2)
            rich_context = "\n".join(paragraphs[start:end])
            
            # 限制长度，防止过长
            if len(rich_context) > 800:
                rich_context = rich_context[:800]
            
            img["rich_context"] = rich_context
            enriched_count += 1
        else:
            # 回退：用原始 caption 作为 rich_context
            img["rich_context"] = caption
    
    print(f"[PDF Parser V3] 图片上下文富化完成: {enriched_count}/{len(images_data)} 张图片成功匹配到 OCR 全文段落")
