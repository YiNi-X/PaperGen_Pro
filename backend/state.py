"""
PaperGen_Pro - LangGraph 状态定义 (V2)

使用 TypedDict 定义 Agent 上下文状态，
管理论文生成工作流中各节点之间的数据传递。
支持多文件上传、图文分离、分章节写作。
"""
from typing import Any, List, Dict, Tuple, TypedDict


class PaperState(TypedDict):
    """LangGraph 工作流的全局状态"""

    # ===== 论文配置 =====
    # 科目 (如 "计算机科学")
    paper_subject: str

    # 论文题目
    paper_title: str

    # 论文语言 ("中文" / "英文")
    paper_language: str

    # 学业类型 ("专科" / "本科" / "研究生")
    academic_type: str

    # 论文水平 ("初级" / "高级")
    paper_level: str

    # 论文类型 ("毕业论文" / "结课论文" / "开题报告" / "任务书" / "文献综述")
    paper_type: str

    # 目标字数 (3000-25000)
    target_word_count: int

    # 中文关键词 (最多4个)
    keywords_cn: List[str]

    # 英文关键词 (最多4个)
    keywords_en: List[str]

    # ===== 解析阶段 =====
    # 原始上传文件字节流列表: [(bytes, filename), ...]
    # 必须在此处定义，否则会被 LangGraph 从初始状态中自动丢弃
    _raw_files: List[Tuple[bytes, str]]

    # PDF 解析后的文本内容（多文件合并后）
    pdf_content: str

    # 是否为扫描件
    is_scanned: bool

    # 提取的图片信息列表
    # 每项: {"path": str, "page": int, "caption_context": str, "source_file": str, "id": str}
    images_data: List[Dict]

    # 提取的参考文献信息列表 (Phase 7 新增)
    # 每项: {"id": str, "text": str}
    references_data: List[Dict]

    # 已经被 AI 选中并排过序的参考文献列表 (Phase 7 新增)
    # 用于最终排版文末的 References 章节以及生成正确的正文上标 [1], [2]
    used_references: List[Dict]

    # RAG 向量检索库 (Phase 3 新增)
    # 存储基于 BAAI/bge-small-zh-v1.5 嵌入的 FAISS 内存索引
    # 用于在 node_write_chapter 时按章节语义检索最相关的原文片段
    vector_store: Any

    # ===== 大纲阶段 =====
    # 用户输入的写作方向 / 意图
    user_intent: str

    # 大纲骨架（仅章节标题，无要点）
    # {"title": "...", "sections": [{"heading": "..."}, ...]}
    outline_skeleton: dict

    # 对抗式大纲 — 变体 A（严谨学术风格）
    # {"title": "...", "sections": [{"heading": "...", "points": [...]}]}
    outline_variant_a: dict

    # 对抗式大纲 — 变体 B（创新发散风格）
    # {"title": "...", "sections": [{"heading": "...", "points": [...]}]}
    outline_variant_b: dict

    # 用户 cherry-pick 合并后的最终大纲 (JSON 格式)
    # {"title": "...", "sections": [{"heading": "...", "points": [...]}]}
    outline: dict

    # AI 审阅意见 / 优化建议
    review_feedback: str

    # ===== 写作阶段 =====
    # 每个章节的生成正文 {"1. 引言": "正文内容...", ...}
    sections_content: Dict[str, str]

    # 最终输出的 Word 文件路径
    final_doc_path: str
