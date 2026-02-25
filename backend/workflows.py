"""
PaperGen_Pro - LangGraph 工作流编排 (V2 - 对抗式大纲)

定义三个独立的 SubGraph，通过 Streamlit session_state 衔接：
  Phase 1 (OutlineGraph):  Parse PDF -> Generate Skeleton -> Generate Variants -> END
  Review  (ReviewGraph):   Review Outline -> END  (cherry-pick 后调用)
  Phase 2 (WritingGraph):  Write Chapters -> Compile Word -> END

人机协同：Phase 1 结束后展示双版本对比，
用户 cherry-pick 合并后触发 ReviewGraph 审阅，
确认后将编辑后的大纲传入 Phase 2 启动写作。
"""
from langgraph.graph import StateGraph, END

from backend.state import PaperState
from backend.nodes import (
    node_parse_pdf,
    node_generate_skeleton,
    node_generate_variants,
    node_review_outline,
    node_write_chapter,
    node_compile_word,
)


def build_outline_graph():
    """
    构建 Phase 1 工作流：骨架生成与双变体填充。

    流转逻辑:
        parse_pdf -> generate_skeleton -> generate_variants -> END

    Returns:
        编译后的 Runnable 对象。
    """
    workflow = StateGraph(PaperState)

    workflow.add_node("parse_pdf", node_parse_pdf)
    workflow.add_node("generate_skeleton", node_generate_skeleton)
    workflow.add_node("generate_variants", node_generate_variants)

    workflow.set_entry_point("parse_pdf")
    workflow.add_edge("parse_pdf", "generate_skeleton")
    workflow.add_edge("generate_skeleton", "generate_variants")
    workflow.add_edge("generate_variants", END)

    return workflow.compile()


def build_review_graph():
    """
    构建审阅工作流：对 cherry-pick 合并后的大纲进行审阅。

    流转逻辑:
        review_outline -> END

    输入: 用户 cherry-pick 合并后的大纲。

    Returns:
        编译后的 Runnable 对象。
    """
    workflow = StateGraph(PaperState)

    workflow.add_node("review_outline", node_review_outline)

    workflow.set_entry_point("review_outline")
    workflow.add_edge("review_outline", END)

    return workflow.compile()


def build_writing_graph():
    """
    构建 Phase 2 工作流：分章节写作与 Word 编译。

    流转逻辑:
        write_chapter -> compile_word -> END

    输入: 用户修改后的大纲 (通过 session_state 传入)。

    Returns:
        编译后的 Runnable 对象。
    """
    workflow = StateGraph(PaperState)

    workflow.add_node("write_chapter", node_write_chapter)
    workflow.add_node("compile_word", node_compile_word)

    workflow.set_entry_point("write_chapter")
    workflow.add_edge("write_chapter", "compile_word")
    workflow.add_edge("compile_word", END)

    return workflow.compile()


# 导出编译好的工作流实例
outline_graph = build_outline_graph()
review_graph = build_review_graph()
writing_graph = build_writing_graph()
