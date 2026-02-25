"""
方案 A: 基于 PyMuPDF 矢量图块检测 + 多模态 API 的公式抓取

原理：
数学公式经常由大量的矢量路径（Path/Drawings）组成（如积分号、横线、括弧），
而不是简单的字体符。
此脚本尝试扫描页面上的 Drawings，按距离聚合成 BBox，
将其裁剪为图片，再传给 Moonshot 视觉大模型识别为 LaTeX 源码。
"""
import os
import base64
from typing import List

import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp", ".env"))
API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
API_BASE = "https://api.moonshot.cn/v1"

if not API_KEY:
    print("❌ 未在 temp/.env 中找到 MOONSHOT_API_KEY。")
    exit(1)


def is_nearby(r1: fitz.Rect, r2: fitz.Rect, threshold: float = 20.0) -> bool:
    """判断两个矩形是否足够接近，可以合并为一个区域。"""
    # 扩展 r1 区域
    r1_expanded = fitz.Rect(
        r1.x0 - threshold, r1.y0 - threshold,
        r1.x1 + threshold, r1.y1 + threshold
    )
    return r1_expanded.intersects(r2)


def merge_rects(rects: List[fitz.Rect], threshold: float = 20.0) -> List[fitz.Rect]:
    """将相近的矩形合并。"""
    if not rects:
        return []

    merged = []
    current_cluster = [rects[0]]

    for r in rects[1:]:
        # 检查是否与当前聚类中的任何矩形相近
        if any(is_nearby(c, r, threshold) for c in current_cluster):
            current_cluster.append(r)
        else:
            # 聚类结合产生大包围盒
            u = current_cluster[0]
            for c in current_cluster[1:]:
                u = u | c
            merged.append(u)
            current_cluster = [r]

    # 收尾最后一个聚类
    if current_cluster:
        u = current_cluster[0]
        for c in current_cluster[1:]:
            u = u | c
        merged.append(u)

    # 有时合并一轮还不够，可能多个不相交的但在扩展范围内可以再合并，简化处理，仅做一次
    return merged


def call_moonshot_formula_ocr(image_path: str) -> str:
    """调用 Moonshot 多模态大模型，要求仅返回 LaTeX 公式。"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    
    response = client.chat.completions.create(
        model="kimi-k2.5",
        temperature=1.0,
        messages=[
            {
                "role": "system",
                "content": "你是一个精确的数学公式识别器。请识别图片中的公式，并严格只输出该公式的 LaTeX 代码，不要包含任何如 '这里是公式：' 之类的解释性文字，也不需要用 `$$` 包裹。"
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    {"type": "text", "text": "请提取图片中的公式内容。"}
                ]
            }
        ]
    )
    return response.choices[0].message.content.strip()


def extract_formulas_via_vectors(pdf_path: str, output_dir: str):
    """主流程：通过矢量图块提取公式。"""
    print(f"📄 加载 PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    os.makedirs(output_dir, exist_ok=True)

    for page_num in range(min(5, len(doc))):  # 为测试速度，仅扫描前5页
        page = doc[page_num]
        drawings = page.get_drawings()
        
        print(f"\n--- 第 {page_num+1} 页，发现 {len(drawings)} 个矢量路径 ---")
        if not drawings:
            continue

        # 取出所有路径的边界框，过滤掉页面边缘的长线条（可能是页眉页脚分割线）
        page_rect = page.rect
        valid_rects = []
        for d in drawings:
            r = d["rect"]
            # 过滤掉宽度或高度极大的线（比如占页宽 80% 的分割线）
            if r.width > page_rect.width * 0.8 or r.height > page_rect.height * 0.8:
                continue
            # 过滤极小的噪点
            if r.width < 5 and r.height < 5:
                continue
            valid_rects.append(r)

        # 合并相近路径（公式通常由多笔划组成密集的一块）
        formula_regions = merge_rects(valid_rects, threshold=30.0)
        
        # 过滤掉合并后仍然偏小的区域（不太可能是完整的公式）
        formula_regions = [r for r in formula_regions if r.width > 20 and r.height > 10]

        print(f"📦 合并后疑似公式区域 ({len(formula_regions)} 个)")

        for idx, rect in enumerate(formula_regions):
            # 将矩形外扩一些，防止公式边缘被恰好截断
            clip_rect = fitz.Rect(
                max(0, rect.x0 - 5),
                max(0, rect.y0 - 5),
                min(page_rect.width, rect.x1 + 5),
                min(page_rect.height, rect.y1 + 5)
            )

            # 渲染该区域为高清图片 (M=2 即 144 DPI)
            pix = page.get_pixmap(clip=clip_rect, matrix=fitz.Matrix(2, 2))
            img_path = os.path.join(output_dir, f"page{page_num+1}_formula{idx+1}.png")
            pix.save(img_path)
            
            print(f"  [{idx+1}] 保存图片至 {img_path}")
            
            # 使用 AI 识别
            try:
                print("  🤖 正在调用多模态大模型进行 OCR...")
                latex = call_moonshot_formula_ocr(img_path)
                print(f"  ✨ 识别结果 LaTeX:\n    {latex}\n")
            except Exception as e:
                print(f"  ❌ 识别失败: {str(e)}")

    doc.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python scheme_a_vector.py <pdf_path>")
        sys.exit(1)
    
    out_dir = os.path.join(os.path.dirname(__file__), "out_scheme_a")
    extract_formulas_via_vectors(sys.argv[1], out_dir)
