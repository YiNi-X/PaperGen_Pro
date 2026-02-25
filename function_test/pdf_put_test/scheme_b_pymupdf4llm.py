"""
方案 B: 使用专用的 PDF 转 Markdown 工具 pymupdf4llm

原理：
pymupdf 官方提供的高阶数据提取库 pymupdf4llm，
内部集成了基于启发式规则或模型的页面解析逻辑，
可以直接将整个 PDF 页面转换为包含公式（$$ $$）的 Markdown 字符串。
此方案代码最少，但对内部逻辑控制较弱。
"""

import sys

try:
    import pymupdf4llm
except ImportError:
    print("❌ 未安装 pymupdf4llm 模块，请运行: pip install pymupdf4llm")
    sys.exit(1)


def extract_formulas_via_pymupdf4llm(pdf_path: str):
    """主流程：通过 pymupdf4llm 将 PDF 转换为 Markdown 文本。"""
    print(f"📄 加载 PDF: {pdf_path}")
    
    try:
        # to_markdown 会自动处理页面结构、表格、图片乃至公式
        # pages=[0,1,2,3,4] 表示仅转换前 5 页进行测试
        md_text = pymupdf4llm.to_markdown(pdf_path, pages=list(range(5)))
        
        print("\n--- 转换结果前 2000 个字符 ---")
        print(md_text[:2000])
        print("...\n")
        
        # 统计其中包含疑似公式的数量 (以 $$ 为标识)
        formula_count = md_text.count("$$") // 2
        inline_formula_count = md_text.count("$") // 2 - formula_count * 2
        
        print(f"📊 文本统计: ")
        print(f"  总字符数: {len(md_text)}")
        print(f"  疑似独立公式段落 ($$): {formula_count} 个")
        print(f"  疑似行内公式 ($): {max(0, inline_formula_count)} 个")
        
    except Exception as e:
        print(f"❌ 转换失败: {str(e)}")

        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scheme_b_pymupdf4llm.py <pdf_path>")
        sys.exit(1)
        
    extract_formulas_via_pymupdf4llm(sys.argv[1])
