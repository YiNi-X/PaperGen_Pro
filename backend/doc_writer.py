"""
PaperGen_Pro - Word 文档生成模块
使用 Pandoc 引擎将 Markdown+LaTeX 一键编译为带有原生 OMML 公式的 Word 文档。
彻底解决排版乱码、字号不齐、公式变图片等痛点。
"""
import os
import re
import config
import pypandoc

def _ensure_pandoc():
    """确保环境中有 pandoc 引擎，如果没有则自动静默下载"""
    try:
        pypandoc.get_pandoc_version()
    except OSError:
        print("[DocWriter] 未检测到系统 Pandoc，正在开始自动下载 (约30MB)...")
        pypandoc.download_pandoc()
        print("[DocWriter] Pandoc 下载及配置完成！")


def generate_docx(
    outline: dict,
    sections_content: dict,
    images_data: list,
    used_references: list = None,
) -> str:
    """
    生成原生的 Word 文档。
    将内容组装为标准 Markdown 文本，并调用 pypandoc 转换为完美排版。
    """
    _ensure_pandoc()

    os.makedirs(config.TEMP_OUTPUT_DIR, exist_ok=True)
    
    # 构建全文 Markdown 巨型字符串
    md_lines = []
    
    # 1. 标题 (Docx 默认会把 Header 1 甚至 Title 认作标题样式)
    title = outline.get("title", "未命名论文")
    md_lines.append(f"# {title}\n")
    
    # 2. 摘要
    abstract_points = outline.get("abstract_points", [])
    if abstract_points:
        md_lines.append("## 摘要\n")
        abstract_text = "；".join(abstract_points) + "。"
        md_lines.append(f"{abstract_text}\n")
        
    # 3. 各章节正文
    img_dict = {img.get("id"): img for img in images_data if img.get("id")}
    sections = outline.get("sections", [])
    
    for section in sections:
        heading = section.get("heading", "")
        # 主章节使用二级标题
        md_lines.append(f"## {heading}\n")
        
        content = sections_content.get(heading, "")
        if content:
            # 替换文献占位符 [REF_ref_001] -> ^[1]^ (Pandoc原生上标语法，避免生成页脚注)
            if used_references:
                for i, ref in enumerate(used_references, 1):
                    ref_id = ref.get("id")
                    content = re.sub(fr'`?\[REF_{ref_id}\]`?', f"^[{i}]^", content)
            
            # 剔除找不到的孤儿占位符，防止它们暴露在正文中
            content = re.sub(r'`?\[REF_[^\]]+\]`?', "", content)

            # 替换图片占位符 [INSERT_IMG_img_001] -> ![图注](绝对物理路径)
            def img_replacer(match):
                img_id = match.group(1)
                img_info = img_dict.get(img_id)
                if img_info:
                    img_info["_inserted"] = True
                    img_path = img_info.get("path", "")
                    # Pandoc 图片路径最好使用正斜杠
                    img_path = img_path.replace("\\", "/")
                    caption = img_info.get("caption_context", "").strip()
                    m = re.search(r'((?:图|Figure|Fig\.?)\s*\d+[^。，\.]+)', caption, re.IGNORECASE)
                    cap_text = m.group(1).strip() if m else "Figure"
                    if not cap_text and caption:
                        cap_text = caption[:80] + "..." if len(caption) > 80 else caption
                        
                    # 添加 Pandoc 专属的图片尺寸限制，防止撑爆 Word 版面
                    return f"\n![{cap_text}]({img_path}){{width=5.5in}}\n"
                return ""
            
            content = re.sub(r'\[INSERT_IMG_([^\]]+)\]', img_replacer, content)
            
            md_lines.append(content)
            md_lines.append("\n")
        else:
            md_lines.append(f"（{heading} 的正文尚未生成）\n\n")
            
    # 4. 附录：未被调用的图片汇总
    remaining_images = [img for img in images_data if not img.get("_inserted", False)]
    if remaining_images:
        md_lines.append("## 附录：图片汇总\n")
        for img_info in remaining_images:
            img_path = img_info.get("path", "").replace("\\", "/")
            caption = img_info.get("caption_context", "Figure").strip()
            caption = caption[:80] + "..." if len(caption) > 80 else caption
            md_lines.append(f"\n![{caption}]({img_path}){{width=5.5in}}\n")
            
    # 5. 附录：参考文献（作为文末列表，而非页脚注）
    if used_references:
        md_lines.append("\n## 参考文献\n")
        for i, ref in enumerate(used_references, 1):
            ref_text = ref.get("text", "").strip()
            md_lines.append(f"{i}. {ref_text}\n")
            
    full_markdown = "\n".join(md_lines)
    
    # 6. 交给 Pandoc 编译
    output_path = os.path.join(config.TEMP_OUTPUT_DIR, "paper_output.docx")
    
    print(f"[DocWriter] 正在启动 Pandoc 编译全文 (字数: {len(full_markdown)})...")
    
    try:
        pypandoc.convert_text(
            source=full_markdown,
            to='docx',
            format='markdown',
            outputfile=output_path,
            extra_args=['--wrap=none'] # 保留原有换行，不强制折行
        )
        print(f"[DocWriter] Word 文档已通过 Pandoc 成功生成原生排版: {output_path}")
    except Exception as e:
        print(f"[DocWriter] Pandoc 编译失败: {e}")
        # fallback 空文档防系统崩溃
        from docx import Document
        doc = Document()
        doc.add_paragraph("Pandoc 编译遇到毁灭性错误，请检查后台日志。")
        doc.save(output_path)
        
    return output_path
