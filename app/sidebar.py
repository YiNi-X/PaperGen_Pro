"""
PaperGen_Pro - 侧边栏组件 (V2)

管理侧边栏导航和全局配置展示。
V2 扩展为 5 步流程。
纯 UI 组件，不包含任何业务逻辑。
"""
import streamlit as st


def render_sidebar():
    """渲染侧边栏：5 步导航 + 项目状态 + 重置按钮。"""

    with st.sidebar:
        st.title("📝 PaperGen Pro")
        st.caption("AI 学术论文辅助写作系统 v2.0")
        st.divider()

        # === 步骤导航 ===
        st.subheader("📌 工作流程")

        steps = [
            ("1️⃣", "上传 PDF 与设定方向"),
            ("2️⃣", "大纲审阅"),
            ("3️⃣", "编辑大纲"),
            ("4️⃣", "正文写作"),
            ("5️⃣", "结果与下载"),
        ]

        current_step = st.session_state.get("current_step", 0)

        for idx, (icon, label) in enumerate(steps):
            if idx < current_step:
                st.markdown(f"✅ ~~{icon} {label}~~")
            elif idx == current_step:
                st.markdown(f"👉 **{icon} {label}**")
            else:
                st.markdown(f"⬜ {icon} {label}")

        st.divider()

        # === Phase 标识 ===
        st.subheader("🔄 当前阶段")
        if current_step <= 2:
            st.info("📋 Phase 1: 解析与大纲")
        else:
            st.info("✍️ Phase 2: 写作与导出")

        # === 解析信息 ===
        if st.session_state.get("phase1_completed", False):
            st.divider()
            st.subheader("📊 文档信息")
            is_scanned = st.session_state.get("is_scanned", False)
            images_count = len(st.session_state.get("images_data", []))
            st.caption(f"类型: {'扫描件' if is_scanned else '电子稿'}")
            st.caption(f"图片: {images_count} 张")
            outline = st.session_state.get("outline", {})
            if outline:
                st.caption(
                    f"章节: {len(outline.get('sections', []))} 个"
                )

        # === 论文配置信息 ===
        paper_title = st.session_state.get("paper_title", "")
        if paper_title:
            st.divider()
            st.subheader("📝 论文配置")
            st.caption(f"科目: {st.session_state.get('paper_subject', '')}")
            st.caption(f"题目: {paper_title}")
            st.caption(f"语言: {st.session_state.get('paper_language', '中文')}")
            st.caption(
                f"类型: {st.session_state.get('academic_type', '本科')} · "
                f"{st.session_state.get('paper_type', '毕业论文')}"
            )
            st.caption(
                f"字数: {st.session_state.get('target_word_count', 8000):,}"
            )

        # === 重置按钮 ===
        st.divider()
        if st.button("🔄 重新开始", use_container_width=True):
            keys_to_clear = [
                "current_step",
                "paper_subject",
                "paper_title",
                "paper_language",
                "academic_type",
                "paper_level",
                "paper_type",
                "target_word_count",
                "keywords_cn",
                "keywords_en",
                "pdf_content",
                "is_scanned",
                "images_data",
                "references_data",
                "used_references",
                "vector_store",
                "user_intent",
                "outline_skeleton",
                "outline_variant_a",
                "outline_variant_b",
                "cherry_picks",
                "outline",
                "review_feedback",
                "sections_content",
                "final_doc_path",
                "phase1_completed",
                "phase2_completed",
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
