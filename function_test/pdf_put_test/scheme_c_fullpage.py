"""
方案 C: 全页渲染 + 多模态结构还原

原理：
最暴力也最准确（如果模型够强）的方案。
不关心页面内部到底是文本还是公式路径，直接把单页 PDF 渲染为高质量图片，
交给如 Moonshot Vision 等多模态大模型，
利用 prompt 让大模型将整页内容转成标准的 Markdown+LaTeX。
"""
import os
import io
import base64

import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp", ".env"))

API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
API_BASE = "https://api.moonshot.cn/v1"

if not API_KEY:
    print("❌ 未在 temp/.env 中找到 MOONSHOT_API_KEY。")
    exit(1)


def call_moonshot_fullpage_ocr(image_bytes: bytes) -> str:
    """调用 Moonshot 多模态 API 对全页进行 OCR 并转换格式。"""
    image_data = base64.b64encode(image_bytes).decode("utf-8")
    
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    
    system_prompt = (
        "你是一个专业的 PDF 解析器和排版还原助手。\n"
        "任务：精确识别提供的文档图片中的所有内容，并完整地还原为 Markdown 格式输出。\n"
        "要求：\n"
        "1. 纯文本内容保持原样的段落结构。\n"
        "2. 文档中的所有数学公式（无论是行内公式还是独立公式），请严格使用 LaTeX 语法输出，并包裹在适当的 `$` 或 `$$` 标签中。\n"
        "3. 表格请使用 Markdown 表格语法还原。\n"
        "4. 忽略页眉、页脚的无关页码，只输出正文和图表题注及公式。\n"
        "5. 不要输出任何多余的开头或结尾寒暄语，直接返回 Markdown 文本即可。"
    )
    
    response = client.chat.completions.create(
        model="kimi-k2.5",
        temperature=1.0,  # kimi-k2.5 只允许使用 temperature=1.0
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    {"type": "text", "text": "请将该页面转换为带公式的 Markdown。"}
                ]
            }
        ]
    )
    return response.choices[0].message.content.strip()


def extract_formulas_via_fullpage_ocr(pdf_path: str, output_dir: str):
    """主流程：将整页转图并多模态解析。"""
    print(f"📄 加载 PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    os.makedirs(output_dir, exist_ok=True)
    
    for page_num in range(min(3, len(doc))):  # 测试速度，仅扫描前3页
        page = doc[page_num]
        
        # 渲染全页为 300 DPI (Matrix(4,4) 左右) 高清图
        print(f"\n--- 正在渲染第 {page_num+1} 页为高清图片 ---")
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
        
        # 将图片保存到内存
        img_bytes = pix.tobytes("png")
        
        # 可选：也保存到磁盘看看原图长什么样
        img_path = os.path.join(output_dir, f"page{page_num+1}_render.png")
        pix.save(img_path)
        print(f"  🖼️ 保存页面截图至 {img_path}")
        
        # 调用大模型识别整页
        print("  🤖 正在发送图片通过多模态 API 识别全页结构 (耗时较长)...")
        try:
            markdown_content = call_moonshot_fullpage_ocr(img_bytes)
            
            md_path = os.path.join(output_dir, f"page{page_num+1}_result.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            print(f"  ✅ 识别成功! 已保存 Markdown 结果至 {md_path}")
            print(f"  👁️ 结果预览 (前 200 字):\n    {markdown_content[:200]} ...\n")
            
        except Exception as e:
            print(f"  ❌ 识别失败: {str(e)}")

    doc.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python scheme_c_fullpage.py <pdf_path>")
        sys.exit(1)
        
    out_dir = os.path.join(os.path.dirname(__file__), "out_scheme_c")
    extract_formulas_via_fullpage_ocr(sys.argv[1], out_dir)
