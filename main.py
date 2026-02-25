"""
PaperGen_Pro - Streamlit 入口文件 (V2)

页面配置、Session State 初始化和 5 步页面导航逻辑。
"""
import streamlit as st

from app.sidebar import render_sidebar
from app.views import (
    view_upload,
    view_outline_review,
    view_outline_editor,
    view_writing_progress,
    view_results,
)


# ===== 页面配置 =====
st.set_page_config(
    page_title="PaperGen Pro v2 - AI 学术论文辅助写作",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===== 初始化 Session State =====
def init_session_state():
    """初始化 Streamlit Session State 的默认值。"""
    defaults = {
        # 导航
        "current_step": 0,
        # 论文配置
        "paper_subject": "计算机科学",
        "paper_title": "",
        "paper_language": "中文",
        "academic_type": "本科",
        "paper_level": "初级",
        "paper_type": "毕业论文",
        "target_word_count": 8000,
        "keywords_cn": [],
        "keywords_en": [],
        # Phase 1 数据
        "pdf_content": "",
        "is_scanned": False,
        "images_data": [],
        "user_intent": "",
        "outline_skeleton": {},
        "outline_variant_a": {},
        "outline_variant_b": {},
        "cherry_picks": {},
        "outline": {},
        "review_feedback": "",
        "phase1_completed": False,
        # Phase 2 数据
        "sections_content": {},
        "final_doc_path": "",
        "phase2_completed": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ===== 主程序 =====
def main():
    """主入口：初始化状态 -> 渲染侧边栏 -> 路由到对应页面。"""
    init_session_state()
    render_sidebar()

    current_step = st.session_state.get("current_step", 0)

    if current_step == 0:
        view_upload()
    elif current_step == 1:
        view_outline_review()
    elif current_step == 2:
        view_outline_editor()
    elif current_step == 3:
        view_writing_progress()
    elif current_step == 4:
        view_results()
    else:
        st.error("未知步骤，请点击侧边栏的「重新开始」。")


if __name__ == "__main__":
    main()
