"""
PaperGen_Pro - 页面视图 (V2)

5 步页面流：
  Step 0: 上传 PDF (支持多文件) + 输入写作方向 -> Phase 1
  Step 1: 大纲审阅 (只读预览 + AI 审阅意见)
  Step 2: 大纲编辑器 (用户修改 JSON 大纲)
  Step 3: 写作进度 (Phase 2 分章节生成)
  Step 4: 最终结果 (查看正文 + 下载 Word)

UI 层只负责展示和状态流转，不处理 AI 调用。
"""
import json
import os

import streamlit as st

from backend.workflows import outline_graph, writing_graph


# =====================================================================
# Step 0: 上传 PDF 与设定方向
# =====================================================================

def view_upload():
    """上传 PDF 文件 (支持 1-5 个) 并配置论文参数，触发 Phase 1。"""

    st.header("📄 第一步：上传论文素材")
    st.markdown(
        "配置论文参数，上传参考论文 PDF，并描述您的写作方向，"
        "AI 将自动解析内容并生成论文大纲。"
    )

    # =====================================================================
    # 科目与题目
    # =====================================================================
    st.subheader("📚 科目与题目")
    st.caption("ℹ️ 不知道怎么选题？只需要输入要求，点击AI推荐题目！")

    subject_list = [
        "计算机科学", "电子信息", "人工智能", "软件工程", "通信工程",
        "机械工程", "电气工程", "土木工程", "化学工程", "材料科学",
        "经济学", "管理学", "金融学", "会计学", "市场营销",
        "法学", "教育学", "心理学", "文学", "历史学",
        "哲学", "社会学", "政治学", "新闻传播", "艺术设计",
        "医学", "护理学", "药学", "生物科学", "环境科学",
        "数学", "物理学", "化学", "农学", "其他",
    ]

    col_subject, col_title, col_ai_btn = st.columns([1.5, 3, 1])

    with col_subject:
        paper_subject = st.selectbox(
            "科目",
            options=subject_list,
            index=subject_list.index(
                st.session_state.get("paper_subject", "计算机科学")
            ),
            key="select_paper_subject",
        )
        st.session_state["paper_subject"] = paper_subject

    with col_title:
        # 处理 AI 推荐题目的待回填值（必须在 widget 实例化之前设置）
        if "_pending_title" in st.session_state:
            st.session_state["input_paper_title"] = st.session_state.pop("_pending_title")

        paper_title = st.text_input(
            "论文题目",
            value=st.session_state.get("paper_title", ""),
            placeholder="请输入 5-50 字论文题目，或输入关键词使用 AI 只能选题！",
            key="input_paper_title",
        )
        st.session_state["paper_title"] = paper_title

    with col_ai_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        ai_title_btn = st.button("🤖 AI推荐题目", type="primary", key="btn_ai_title")

    # AI 推荐题目逻辑
    if ai_title_btn:
        user_hint = paper_title.strip() or st.session_state.get("user_intent", "")
        if not user_hint:
            st.warning("⚠️ 请先输入一些关键词或写作方向，以便 AI 推荐题目。")
        else:
            try:
                with st.spinner("🤖 AI 正在为您推荐题目..."):
                    from backend.services import call_deepseek_recommend_title
                    titles = call_deepseek_recommend_title(
                        subject=paper_subject,
                        user_intent=user_hint,
                    )
                if titles:
                    st.session_state["_recommended_titles"] = titles
                else:
                    st.warning("⚠️ AI 未能生成推荐题目，请尝试修改关键词后重试。")
            except Exception as e:
                st.error(f"❌ AI 推荐题目失败: {e}")

    # 显示推荐的题目
    recommended_titles = st.session_state.get("_recommended_titles", [])
    if recommended_titles:
        st.markdown("**🎯 AI 推荐题目** （点击选择）：")
        cols = st.columns(len(recommended_titles))
        for idx, title in enumerate(recommended_titles):
            with cols[idx]:
                if st.button(
                    title,
                    key=f"rec_title_{idx}",
                    use_container_width=True,
                ):
                    st.session_state["paper_title"] = title
                    st.session_state["_pending_title"] = title
                    st.session_state["_recommended_titles"] = []
                    st.rerun()

    st.divider()

    # =====================================================================
    # 论文语言 / 学业类型 / 论文水平
    # =====================================================================
    col_lang, col_academic, col_level = st.columns(3)

    with col_lang:
        st.subheader("🌐 论文语言")
        paper_language = st.selectbox(
            "语言",
            options=["中文", "英文"],
            index=["中文", "英文"].index(
                st.session_state.get("paper_language", "中文")
            ),
            key="select_paper_language",
            label_visibility="collapsed",
        )
        st.session_state["paper_language"] = paper_language

    with col_academic:
        st.subheader("🎓 学业类型")
        academic_options = ["专科", "本科", "研究生"]
        academic_type = st.radio(
            "学业类型",
            options=academic_options,
            index=academic_options.index(
                st.session_state.get("academic_type", "本科")
            ),
            horizontal=True,
            key="radio_academic_type",
            label_visibility="collapsed",
        )
        st.session_state["academic_type"] = academic_type

    with col_level:
        st.subheader("📊 论文水平")
        level_options = ["初级", "高级"]
        paper_level = st.radio(
            "论文水平",
            options=level_options,
            index=level_options.index(
                st.session_state.get("paper_level", "初级")
            ),
            horizontal=True,
            key="radio_paper_level",
            label_visibility="collapsed",
        )
        st.session_state["paper_level"] = paper_level

    st.divider()

    # =====================================================================
    # 论文类型
    # =====================================================================
    st.subheader("📋 论文类型")
    paper_type_options = ["毕业论文", "结课论文", "开题报告", "任务书", "文献综述"]
    paper_type = st.radio(
        "论文类型",
        options=paper_type_options,
        index=paper_type_options.index(
            st.session_state.get("paper_type", "毕业论文")
        ),
        horizontal=True,
        key="radio_paper_type",
        label_visibility="collapsed",
    )
    st.session_state["paper_type"] = paper_type

    st.divider()

    # =====================================================================
    # 论文字数
    # =====================================================================
    st.subheader("📝 论文字数")
    st.caption("字数供参考，可能存在误差，属于正常情况。")
    target_word_count = st.slider(
        "目标字数",
        min_value=3000,
        max_value=25000,
        value=st.session_state.get("target_word_count", 8000),
        step=1000,
        format="%d",
        key="slider_word_count",
        label_visibility="collapsed",
    )
    st.session_state["target_word_count"] = target_word_count

    # 字数刻度说明
    marks_cols = st.columns(9)
    mark_labels = ["3000", "5000", "8000", "10000", "12000",
                   "15000", "18000", "20000", "25000"]
    for i, label in enumerate(mark_labels):
        with marks_cols[i]:
            val = int(label)
            if val > 15000:
                st.markdown(
                    f"<span style='color: #e74c3c; font-size: 12px;'>"
                    f"{label}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<span style='font-size: 12px;'>{label}</span>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # =====================================================================
    # PDF 上传
    # =====================================================================
    st.subheader("📎 上传参考论文 PDF")
    uploaded_files = st.file_uploader(
        "上传 PDF 文件（支持多选）",
        type=["pdf"],
        accept_multiple_files=True,
        help="支持最大 50MB 的 PDF 文件，最多同时上传 5 个",
    )

    if uploaded_files and len(uploaded_files) > 5:
        st.warning("⚠️ 最多支持 5 个文件，请减少文件数量。")
        uploaded_files = uploaded_files[:5]

    if uploaded_files:
        st.success(f"✅ 已选择 {len(uploaded_files)} 个文件：")
        for f in uploaded_files:
            size_mb = len(f.getvalue()) / (1024 * 1024)
            st.caption(f"  📎 {f.name} ({size_mb:.1f} MB)")

    # =====================================================================
    # 写作方向输入
    # =====================================================================
    user_intent = st.text_area(
        "✍️ 请描述您的写作方向",
        placeholder=(
            "例如：我希望围绕「大语言模型在教育领域的应用」这个主题，"
            "重点分析 GPT-4 和 DeepSeek 在自动评分和个性化辅导方面的表现..."
        ),
        height=120,
    )

    st.divider()

    # =====================================================================
    # 中英文关键词
    # =====================================================================
    st.subheader("🔑 关键词")

    col_kw_cn, col_kw_en = st.columns(2)

    with col_kw_cn:
        st.markdown("**中文关键词** <span style='color: gray; font-size: 12px;'>"
                     "关键词上限4个，可删除后自定义关键词</span>",
                     unsafe_allow_html=True)

        # 显示已有关键词标签
        keywords_cn = st.session_state.get("keywords_cn", [])
        if keywords_cn:
            kw_cols = st.columns(len(keywords_cn) + 1)
            for idx, kw in enumerate(keywords_cn):
                with kw_cols[idx]:
                    if st.button(f"❌ {kw}", key=f"del_kw_cn_{idx}"):
                        st.session_state["keywords_cn"].pop(idx)
                        st.rerun()

        # 添加新关键词
        cn_col_input, cn_col_btn = st.columns([3, 1])
        with cn_col_input:
            new_kw_cn = st.text_input(
                "添加中文关键词",
                placeholder="关键词上限4个，可删除后自定义关键词",
                key="input_kw_cn",
                label_visibility="collapsed",
            )
        with cn_col_btn:
            if st.button("➕ 添加", key="btn_add_kw_cn"):
                if new_kw_cn.strip() and len(keywords_cn) < 4:
                    st.session_state["keywords_cn"].append(new_kw_cn.strip())
                    st.rerun()
                elif len(keywords_cn) >= 4:
                    st.warning("⚠️ 最多 4 个中文关键词")

    with col_kw_en:
        st.markdown("**英文关键词** <span style='color: gray; font-size: 12px;'>"
                     "关键词上限4个，可删除后自定义关键词</span>",
                     unsafe_allow_html=True)

        # 显示已有关键词标签
        keywords_en = st.session_state.get("keywords_en", [])
        if keywords_en:
            kw_cols = st.columns(len(keywords_en) + 1)
            for idx, kw in enumerate(keywords_en):
                with kw_cols[idx]:
                    if st.button(f"❌ {kw}", key=f"del_kw_en_{idx}"):
                        st.session_state["keywords_en"].pop(idx)
                        st.rerun()

        # 添加新关键词
        en_col_input, en_col_btn = st.columns([3, 1])
        with en_col_input:
            new_kw_en = st.text_input(
                "添加英文关键词",
                placeholder="关键词上限4个，可删除后自定义关键词",
                key="input_kw_en",
                label_visibility="collapsed",
            )
        with en_col_btn:
            if st.button("➕ 添加", key="btn_add_kw_en"):
                if new_kw_en.strip() and len(keywords_en) < 4:
                    st.session_state["keywords_en"].append(new_kw_en.strip())
                    st.rerun()
                elif len(keywords_en) >= 4:
                    st.warning("⚠️ 最多 4 个英文关键词")

    # AI 自动生成关键词按钮
    ai_kw_btn = st.button(
        "🤖 AI 自动生成关键词",
        key="btn_ai_keywords",
        disabled=(not st.session_state.get("paper_title", "").strip()),
    )
    if ai_kw_btn:
        try:
            with st.spinner("🤖 AI 正在生成关键词..."):
                from backend.services import call_deepseek_generate_keywords
                kw_result = call_deepseek_generate_keywords(
                    title=st.session_state.get("paper_title", ""),
                    subject=st.session_state.get("paper_subject", ""),
                    user_intent=user_intent.strip() or st.session_state.get(
                        "paper_title", ""
                    ),
                )
            if kw_result.get("cn"):
                st.session_state["keywords_cn"] = kw_result["cn"][:4]
            if kw_result.get("en"):
                st.session_state["keywords_en"] = kw_result["en"][:4]
            st.rerun()
        except Exception as e:
            st.error(f"❌ AI 生成关键词失败: {e}")

    st.divider()

    # =====================================================================
    # 触发 Phase 1
    # =====================================================================
    col1, col2 = st.columns([1, 3])
    with col1:
        run_button = st.button(
            "🚀 开始生成",
            type="primary",
            use_container_width=True,
            disabled=(not uploaded_files or not user_intent.strip()),
        )

    if run_button and uploaded_files:
        # 读取所有文件的字节数据
        raw_files = []
        for f in uploaded_files:
            raw_files.append((f.read(), f.name))

        # 构建初始状态（包含论文配置）
        initial_state = {
            "paper_subject": st.session_state.get("paper_subject", ""),
            "paper_title": st.session_state.get("paper_title", ""),
            "paper_language": st.session_state.get("paper_language", "中文"),
            "academic_type": st.session_state.get("academic_type", "本科"),
            "paper_level": st.session_state.get("paper_level", "初级"),
            "paper_type": st.session_state.get("paper_type", "毕业论文"),
            "target_word_count": st.session_state.get("target_word_count", 8000),
            "keywords_cn": st.session_state.get("keywords_cn", []),
            "keywords_en": st.session_state.get("keywords_en", []),
            "pdf_content": "",
            "is_scanned": False,
            "images_data": [],
            "user_intent": user_intent.strip(),
            "outline": {},
            "review_feedback": "",
            "sections_content": {},
            "final_doc_path": "",
            "_raw_files": raw_files,
        }

        # 执行 Phase 1: 解析 -> 大纲 -> 审阅
        try:
            with st.spinner("🔄 AI 正在处理中，请稍候..."):
                progress_bar = st.progress(0, text="正在解析 PDF...")

                final_state = {}
                step_count = 0
                total_steps = 3

                for event in outline_graph.stream(initial_state):
                    step_count += 1
                    progress = min(step_count / total_steps, 1.0)

                    if "parse_pdf" in event:
                        progress_bar.progress(
                            progress,
                            text=f"✅ PDF 解析完成 "
                                 f"(图片: {len(event['parse_pdf'].get('images_data', []))} 张)，"
                                 f"正在生成大纲骨架..."
                        )
                        final_state.update(event["parse_pdf"])

                    elif "generate_skeleton" in event:
                        sections_count = len(
                            event["generate_skeleton"]
                            .get("outline_skeleton", {})
                            .get("sections", [])
                        )
                        progress_bar.progress(
                            progress,
                            text=f"✅ 骨架生成完成 ({sections_count} 个章节)，"
                                 f"正在生成双版本大纲..."
                        )
                        final_state.update(event["generate_skeleton"])

                    elif "generate_variants" in event:
                        progress_bar.progress(progress, text="✅ 双版本大纲生成完成！")
                        final_state.update(event["generate_variants"])

                progress_bar.progress(1.0, text="🎉 Phase 1 全部完成！")

            # 保存到 session_state
            if final_state:
                st.session_state["pdf_content"] = final_state.get("pdf_content", "")
                st.session_state["is_scanned"] = final_state.get("is_scanned", False)
                st.session_state["images_data"] = final_state.get("images_data", [])
                st.session_state["user_intent"] = user_intent
                st.session_state["outline_skeleton"] = final_state.get(
                    "outline_skeleton", {}
                )
                st.session_state["outline_variant_a"] = final_state.get(
                    "outline_variant_a", {}
                )
                st.session_state["outline_variant_b"] = final_state.get(
                    "outline_variant_b", {}
                )
                st.session_state["cherry_picks"] = {}
                st.session_state["outline"] = {}
                st.session_state["review_feedback"] = ""
                st.session_state["phase1_completed"] = True
                st.session_state["current_step"] = 1
                st.rerun()

        except Exception as e:
            error_msg = str(e)
            if "402" in error_msg or "Insufficient Balance" in error_msg:
                st.error(
                    "❌ **API 余额不足**\n\n"
                    "您的 DeepSeek API 账户余额不足，请前往 "
                    "[DeepSeek 控制台](https://platform.deepseek.com/) 充值后重试。"
                )
            elif "401" in error_msg or "Unauthorized" in error_msg:
                st.error(
                    "❌ **API Key 无效**\n\n"
                    "请检查 `.env` 文件中的 `DEEPSEEK_API_KEY` 是否正确。"
                )
            else:
                st.error(f"❌ **AI 处理出错**: {error_msg}")
            st.info("💡 请解决上述问题后，重新点击「开始生成」按钮。")

    # =====================================================================
    # 🛠️ 开发调试面板（仅开发阶段显示，发布前删除此段）
    # =====================================================================
    if st.session_state.get("debug_mode", False):
        st.divider()
        with st.expander("🛠️ 开发调试面板 — 查看配置如何影响 AI Prompt", expanded=True):
            # --- 当前配置一览 ---
            st.markdown("### 📋 当前论文配置")
            debug_config = {
                "科目 (paper_subject)": st.session_state.get("paper_subject", ""),
                "题目 (paper_title)": st.session_state.get("paper_title", ""),
                "语言 (paper_language)": st.session_state.get("paper_language", "中文"),
                "学业类型 (academic_type)": st.session_state.get("academic_type", "本科"),
                "论文水平 (paper_level)": st.session_state.get("paper_level", "初级"),
                "论文类型 (paper_type)": st.session_state.get("paper_type", "毕业论文"),
                "目标字数 (target_word_count)": st.session_state.get("target_word_count", 8000),
                "中文关键词 (keywords_cn)": st.session_state.get("keywords_cn", []),
                "英文关键词 (keywords_en)": st.session_state.get("keywords_en", []),
            }
            for label, val in debug_config.items():
                st.text(f"  {label}: {val}")

            st.markdown("---")

            # --- 模拟 Prompt 片段 ---
            st.markdown("### 🧠 大纲生成 Prompt 中的配置段")
            st.markdown(
                "以下是 `call_deepseek_generate_outline()` 发送给 AI 的 "
                "**论文配置信息段**（system prompt 的追加部分）："
            )

            _subject = st.session_state.get("paper_subject", "未指定")
            _title = st.session_state.get("paper_title", "未指定")
            _lang = st.session_state.get("paper_language", "中文")
            _academic = st.session_state.get("academic_type", "本科")
            _level = st.session_state.get("paper_level", "初级")
            _ptype = st.session_state.get("paper_type", "毕业论文")
            _wcount = st.session_state.get("target_word_count", 8000)
            _kw_cn = st.session_state.get("keywords_cn", [])
            _kw_en = st.session_state.get("keywords_en", [])

            outline_prompt_segment = (
                f"论文配置信息：\n"
                f"- 科目: {_subject}\n"
                f"- 题目: {_title}\n"
                f"- 语言: {_lang}\n"
                f"- 学业类型: {_academic}\n"
                f"- 论文水平: {_level}\n"
                f"- 论文类型: {_ptype}\n"
                f"- 目标字数: {_wcount}\n"
                f"- 中文关键词: {', '.join(_kw_cn) if _kw_cn else '(无)'}\n"
                f"- 英文关键词: {', '.join(_kw_en) if _kw_en else '(无)'}\n"
                f"\n"
                f"请严格按照以上配置生成大纲，特别注意：\n"
                f"1. 使用指定的论文语言撰写\n"
                f"2. 章节数量和深度应符合学业类型和论文水平要求\n"
                f"3. 目标总字数约 {_wcount} 字，合理分配各章节字数\n"
                f"4. 论文类型为「{_ptype}」，请遵循对应的格式规范"
            )
            st.code(outline_prompt_segment, language="text")

            st.markdown("---")

            # --- 章节写作 Prompt 片段 ---
            st.markdown("### ✍️ 章节写作 Prompt 中的配置段")
            st.markdown(
                "以下是 `call_deepseek_write_chapter()` 发送给 AI 的 "
                "**写作指导追加段**（附加在 system prompt 末尾）："
            )

            _sections_n = 6  # 假设 6 个章节用于演示
            _wps = _wcount // max(_sections_n, 1)
            writing_prompt_segment = (
                f"7. 使用{_lang}撰写\n"
                f"8. 写作水平要求：{_academic}{_level}级别\n"
                f"9. 本章节目标字数约 {_wps} 字\n"
                f"   (总字数 {_wcount} ÷ 假设 {_sections_n} 章 = {_wps} 字/章)"
            )
            st.code(writing_prompt_segment, language="text")

            st.markdown("---")
            st.caption(
                "💡 提示：此面板仅开发阶段显示。"
                "在侧边栏底部可切换调试模式。"
                "发布前在 sidebar.py 和 views.py 中删除 debug_mode 相关代码即可。"
            )


# =====================================================================
# Step 1: 大纲对比与选择 (对抗式 Cherry-pick)
# =====================================================================

def view_outline_review():
    """双版本大纲对比，用户逐要点 cherry-pick 合并。"""

    st.header("📋 第二步：大纲对比与选择")
    st.markdown(
        "AI 基于相同的章节框架生成了两份风格不同的大纲。"
        "请在每个章节中 **勾选您喜欢的要点**，自由混搭组合。"
    )

    variant_a = st.session_state.get("outline_variant_a", {})
    variant_b = st.session_state.get("outline_variant_b", {})
    skeleton = st.session_state.get("outline_skeleton", {})

    if not variant_a or not variant_b:
        st.warning("⚠️ 未找到双版本大纲数据，请返回上一步重新生成。")
        if st.button("⬅️ 返回重新上传"):
            st.session_state["current_step"] = 0
            st.rerun()
        return

    sections_a = variant_a.get("sections", [])
    sections_b = variant_b.get("sections", [])
    title = skeleton.get("title", variant_a.get("title", "未命名论文"))

    st.markdown(f"### 📖 {title}")

    # 初始化 cherry_picks
    if not st.session_state.get("cherry_picks"):
        cherry_picks = {}
        for idx in range(max(len(sections_a), len(sections_b))):
            pts_a = sections_a[idx].get("points", []) if idx < len(sections_a) else []
            pts_b = sections_b[idx].get("points", []) if idx < len(sections_b) else []
            cherry_picks[str(idx)] = {
                "a": [False] * len(pts_a),
                "b": [False] * len(pts_b),
            }
        st.session_state["cherry_picks"] = cherry_picks

    cherry_picks = st.session_state["cherry_picks"]

    st.divider()

    # === 逐章节对比 ===
    num_sections = max(len(sections_a), len(sections_b))
    for idx in range(num_sections):
        sec_a = sections_a[idx] if idx < len(sections_a) else {}
        sec_b = sections_b[idx] if idx < len(sections_b) else {}

        heading = sec_a.get("heading", sec_b.get("heading", f"第 {idx + 1} 章"))
        points_a = sec_a.get("points", [])
        points_b = sec_b.get("points", [])

        # 确保 cherry_picks 结构存在
        if str(idx) not in cherry_picks:
            cherry_picks[str(idx)] = {
                "a": [False] * len(points_a),
                "b": [False] * len(points_b),
            }

        st.subheader(f"📌 {heading}")
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("🅰️ **版本 A** — 严谨学术")
            for pi, point in enumerate(points_a):
                checked = cherry_picks[str(idx)]["a"][pi] if pi < len(cherry_picks[str(idx)]["a"]) else False
                val = st.checkbox(
                    point,
                    value=checked,
                    key=f"cp_a_{idx}_{pi}",
                )
                # 同步到 cherry_picks
                while len(cherry_picks[str(idx)]["a"]) <= pi:
                    cherry_picks[str(idx)]["a"].append(False)
                cherry_picks[str(idx)]["a"][pi] = val

        with col_b:
            st.markdown("🅱️ **版本 B** — 创新发散")
            for pi, point in enumerate(points_b):
                checked = cherry_picks[str(idx)]["b"][pi] if pi < len(cherry_picks[str(idx)]["b"]) else False
                val = st.checkbox(
                    point,
                    value=checked,
                    key=f"cp_b_{idx}_{pi}",
                )
                while len(cherry_picks[str(idx)]["b"]) <= pi:
                    cherry_picks[str(idx)]["b"].append(False)
                cherry_picks[str(idx)]["b"][pi] = val

        # 显示已选要点摘要
        selected = []
        for pi, point in enumerate(points_a):
            if pi < len(cherry_picks[str(idx)]["a"]) and cherry_picks[str(idx)]["a"][pi]:
                selected.append(f"A-{pi+1}")
        for pi, point in enumerate(points_b):
            if pi < len(cherry_picks[str(idx)]["b"]) and cherry_picks[str(idx)]["b"][pi]:
                selected.append(f"B-{pi+1}")
        st.caption(f"✅ 已选: {', '.join(selected) if selected else '(无)'}")

        st.divider()

    # === 合并预览 ===
    with st.expander("👁️ 合并大纲预览", expanded=False):
        merged = _build_merged_outline(sections_a, sections_b, cherry_picks, title)
        for sec in merged.get("sections", []):
            st.markdown(f"**{sec.get('heading', '')}**")
            for pt in sec.get("points", []):
                st.markdown(f"  - {pt}")

    # === 操作按钮 ===
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ 返回重新上传", use_container_width=True):
            st.session_state["current_step"] = 0
            st.rerun()
    with col2:
        if st.button("🔄 重新生成大纲", use_container_width=True):
            st.session_state["current_step"] = 0
            st.session_state["phase1_completed"] = False
            st.rerun()
    with col3:
        confirm_btn = st.button(
            "✅ 确认合并大纲 → 审阅",
            type="primary",
            use_container_width=True,
        )

    if confirm_btn:
        merged = _build_merged_outline(sections_a, sections_b, cherry_picks, title)
        st.session_state["outline"] = merged

        # 调用 review_graph 审阅合并后的大纲
        try:
            with st.spinner("🧐 AI 正在审阅合并后的大纲..."):
                from backend.workflows import review_graph

                review_state = {
                    "outline": merged,
                    # 填充必要的默认值以满足 PaperState
                    "pdf_content": st.session_state.get("pdf_content", ""),
                    "user_intent": st.session_state.get("user_intent", ""),
                    "review_feedback": "",
                }
                final = {}
                for event in review_graph.stream(review_state):
                    if "review_outline" in event:
                        final.update(event["review_outline"])

                st.session_state["review_feedback"] = final.get(
                    "review_feedback", ""
                )

            st.session_state["current_step"] = 2
            st.rerun()

        except Exception as e:
            st.error(f"❌ 审阅失败: {e}")

    # === 审阅意见显示（如果已有） ===
    review_feedback = st.session_state.get("review_feedback", "")
    if review_feedback:
        st.divider()
        st.subheader("📝 AI 审阅意见")
        st.markdown(review_feedback)


def _build_merged_outline(
    sections_a: list,
    sections_b: list,
    cherry_picks: dict,
    title: str,
) -> dict:
    """根据 cherry_picks 合并两个变体的要点为一份大纲。"""
    merged_sections = []
    num_sections = max(len(sections_a), len(sections_b))

    for idx in range(num_sections):
        sec_a = sections_a[idx] if idx < len(sections_a) else {}
        sec_b = sections_b[idx] if idx < len(sections_b) else {}

        heading = sec_a.get("heading", sec_b.get("heading", f"第 {idx + 1} 章"))
        points_a = sec_a.get("points", [])
        points_b = sec_b.get("points", [])

        picks = cherry_picks.get(str(idx), {"a": [], "b": []})
        merged_points = []

        for pi, point in enumerate(points_a):
            if pi < len(picks.get("a", [])) and picks["a"][pi]:
                merged_points.append(point)

        for pi, point in enumerate(points_b):
            if pi < len(picks.get("b", [])) and picks["b"][pi]:
                merged_points.append(point)

        merged_sections.append({
            "heading": heading,
            "points": merged_points,
        })

    return {"title": title, "sections": merged_sections}


# =====================================================================
# Step 2: 大纲编辑器 (人机协同)
# =====================================================================

def view_outline_editor():
    """用户编辑大纲 JSON，确认后触发 Phase 2 写作。"""

    st.header("✏️ 第三步：编辑大纲")
    st.markdown(
        "您可以直接修改下方的 JSON 大纲内容，"
        "调整章节结构、标题和要点。确认后点击按钮开始撰写正文。"
    )

    outline = st.session_state.get("outline", {})

    # === JSON 编辑区域 ===
    outline_json_str = json.dumps(outline, ensure_ascii=False, indent=2)

    edited_json = st.text_area(
        "📝 编辑大纲 (JSON 格式)",
        value=outline_json_str,
        height=500,
        help="请保持 JSON 格式正确，修改 title、sections、points 等字段",
    )

    # === JSON 格式 + 结构验证 ===
    json_valid = True
    parsed_outline = outline
    try:
        parsed_outline = json.loads(edited_json)

        # --- 结构校验 ---
        schema_errors = []
        if not isinstance(parsed_outline.get("title"), str) or not parsed_outline["title"].strip():
            schema_errors.append("缺少 `title` 字段或为空")
        sections = parsed_outline.get("sections")
        if not isinstance(sections, list) or len(sections) == 0:
            schema_errors.append("缺少 `sections` 字段或为空列表")
        else:
            for i, sec in enumerate(sections):
                if not isinstance(sec.get("heading"), str) or not sec["heading"].strip():
                    schema_errors.append(f"第 {i+1} 个章节缺少 `heading`")
                if not isinstance(sec.get("points"), list):
                    schema_errors.append(f"第 {i+1} 个章节缺少 `points` 列表")

        if schema_errors:
            st.error("❌ 大纲结构不完整：\n- " + "\n- ".join(schema_errors))
            json_valid = False
        else:
            st.success("✅ JSON 格式与结构校验通过")

        # 快速预览
        with st.expander("👁️ 预览编辑后的大纲"):
            title = parsed_outline.get("title", "未命名")
            st.markdown(f"**标题**: {title}")
            for sec in parsed_outline.get("sections", []):
                st.markdown(f"- **{sec.get('heading', '')}**: "
                            f"{', '.join(sec.get('points', []))}")

    except json.JSONDecodeError as e:
        st.error(f"❌ JSON 格式错误: {e}")
        json_valid = False

    st.divider()

    # === 操作按钮 ===
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ 返回审阅", use_container_width=True):
            st.session_state["current_step"] = 1
            st.rerun()
    with col2:
        if st.button("🔄 重置为原始大纲", use_container_width=True):
            st.rerun()  # text_area 会恢复到 session_state 的值
    with col3:
        start_writing = st.button(
            "🚀 开始撰写正文 (Phase 2)",
            type="primary",
            use_container_width=True,
            disabled=(not json_valid),
        )

    if start_writing and json_valid:
        # 保存编辑后的大纲
        st.session_state["outline"] = parsed_outline
        st.session_state["current_step"] = 3
        st.rerun()


# =====================================================================
# Step 3: 写作进度
# =====================================================================

def view_writing_progress():
    """Phase 2 执行：分章节写作 + 编译 Word。"""

    st.header("📝 第四步：正文写作")

    outline = st.session_state.get("outline", {})
    sections = outline.get("sections", [])

    # 如果尚未开始写作，立即执行
    if not st.session_state.get("phase2_completed", False):
        st.markdown(
            f"AI 正在根据您确认的大纲撰写正文"
            f"（共 {len(sections)} 个章节）..."
        )

        # 构建 Phase 2 初始状态（包含论文配置）
        phase2_state = {
            "paper_subject": st.session_state.get("paper_subject", ""),
            "paper_title": st.session_state.get("paper_title", ""),
            "paper_language": st.session_state.get("paper_language", "中文"),
            "academic_type": st.session_state.get("academic_type", "本科"),
            "paper_level": st.session_state.get("paper_level", "初级"),
            "paper_type": st.session_state.get("paper_type", "毕业论文"),
            "target_word_count": st.session_state.get("target_word_count", 8000),
            "keywords_cn": st.session_state.get("keywords_cn", []),
            "keywords_en": st.session_state.get("keywords_en", []),
            "pdf_content": st.session_state.get("pdf_content", ""),
            "is_scanned": st.session_state.get("is_scanned", False),
            "images_data": st.session_state.get("images_data", []),
            "user_intent": st.session_state.get("user_intent", ""),
            "outline": outline,
            "review_feedback": st.session_state.get("review_feedback", ""),
            "sections_content": {},
            "final_doc_path": "",
        }

        try:
            with st.spinner("🔄 AI 正在撰写论文..."):
                progress_bar = st.progress(0, text="正在撰写章节...")

                final_state = {}
                step_count = 0
                total_steps = 2  # write_chapter, compile_word

                for event in writing_graph.stream(phase2_state):
                    step_count += 1
                    progress = min(step_count / total_steps, 1.0)

                    if "write_chapter" in event:
                        written = len(
                            event["write_chapter"].get("sections_content", {})
                        )
                        progress_bar.progress(
                            progress,
                            text=f"✅ 章节写作完成 ({written}/{len(sections)} 章)，"
                                 f"正在编译 Word..."
                        )
                        final_state.update(event["write_chapter"])

                    elif "compile_word" in event:
                        progress_bar.progress(progress, text="✅ Word 文档编译完成！")
                        final_state.update(event["compile_word"])

                progress_bar.progress(1.0, text="🎉 Phase 2 全部完成！")

            # 保存结果
            if final_state:
                st.session_state["sections_content"] = final_state.get(
                    "sections_content", {}
                )
                st.session_state["final_doc_path"] = final_state.get(
                    "final_doc_path", ""
                )
                st.session_state["phase2_completed"] = True
                st.rerun()

        except Exception as e:
            error_msg = str(e)
            if "402" in error_msg or "Insufficient Balance" in error_msg:
                st.error(
                    "❌ **API 余额不足**\n\n"
                    "您的 DeepSeek API 账户余额不足，请前往 "
                    "[DeepSeek 控制台](https://platform.deepseek.com/) 充值后重试。"
                )
            elif "401" in error_msg or "Unauthorized" in error_msg:
                st.error(
                    "❌ **API Key 无效**\n\n"
                    "请检查 `.env` 文件中的 `DEEPSEEK_API_KEY` 是否正确。"
                )
            else:
                st.error(f"❌ **AI 处理出错**: {error_msg}")
            st.info("💡 请解决上述问题后，返回编辑大纲页面重试。")

    else:
        # 写作已完成，显示章节内容
        st.success("✅ 全部章节写作完成！")
        sections_content = st.session_state.get("sections_content", {})

        for section in sections:
            heading = section.get("heading", "")
            content = sections_content.get(heading, "（未生成）")
            with st.expander(f"📖 {heading}", expanded=False):
                st.markdown(content)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ 返回编辑大纲", use_container_width=True):
                st.session_state["phase2_completed"] = False
                st.session_state["current_step"] = 2
                st.rerun()
        with col2:
            if st.button(
                "📥 查看结果与下载",
                type="primary",
                use_container_width=True,
            ):
                st.session_state["current_step"] = 4
                st.rerun()


# =====================================================================
# Step 4: 最终结果展示
# =====================================================================

def view_results():
    """展示最终结果：论文内容 + Word 下载。"""

    st.header("🎉 第五步：结果总览")

    outline = st.session_state.get("outline", {})
    sections_content = st.session_state.get("sections_content", {})
    images_data = st.session_state.get("images_data", [])
    final_doc_path = st.session_state.get("final_doc_path", "")

    # === 论文标题 ===
    st.markdown(f"## 📖 {outline.get('title', '未命名论文')}")

    # === 统计信息 ===
    total_chars = sum(len(v) for v in sections_content.values())
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 总章节数", len(sections_content))
    with col2:
        st.metric("📝 总字数", f"{total_chars:,}")
    with col3:
        st.metric("🖼️ 图片数", len(images_data))

    st.divider()

    # === 全文预览 ===
    st.subheader("📄 全文预览")
    for section in outline.get("sections", []):
        heading = section.get("heading", "")
        content = sections_content.get(heading, "")
        if content:
            with st.expander(f"📌 {heading}", expanded=False):
                st.markdown(content)

    st.divider()

    # === 导出区域 ===
    st.subheader("📥 导出下载")
    col1, col2, col3 = st.columns(3)

    with col1:
        # 下载大纲
        if outline:
            st.download_button(
                label="📋 下载大纲 (JSON)",
                data=json.dumps(outline, ensure_ascii=False, indent=2),
                file_name="paper_outline.json",
                mime="application/json",
                use_container_width=True,
            )

    with col2:
        # 下载 Word 文档
        if final_doc_path and os.path.exists(final_doc_path):
            with open(final_doc_path, "rb") as f:
                st.download_button(
                    label="📄 下载论文 (Word)",
                    data=f.read(),
                    file_name="paper_output.docx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    use_container_width=True,
                )
        else:
            st.button(
                "📄 Word 文件不可用",
                disabled=True,
                use_container_width=True,
            )

    with col3:
        # 下载 Markdown 全文
        full_md = f"# {outline.get('title', '未命名')}\n\n"
        for section in outline.get("sections", []):
            heading = section.get("heading", "")
            content = sections_content.get(heading, "")
            full_md += f"\n{content}\n"

        st.download_button(
            label="📝 下载全文 (Markdown)",
            data=full_md,
            file_name="paper_full.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.divider()

    # === 返回按钮 ===
    if st.button("⬅️ 返回写作页面", use_container_width=True):
        st.session_state["current_step"] = 3
        st.rerun()
