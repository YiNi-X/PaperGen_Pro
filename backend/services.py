"""
PaperGen_Pro - 底层 API 调用服务 (V2)

封装 DeepSeek (写作/大纲), 多模态 OCR 的 API 调用。
V2 移除了 Kimi file-extract（改用本地 PyMuPDF），
新增多模态 OCR 和分章节写作服务。
"""
import base64
import json

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

import config
import re

def _extract_json_from_text(text: str, func_name: str = "Unknown"):
    """
    通用、高容错的 JSON 提取器。
    专门应对大模型 (如 DeepSeek R1) 在真正 JSON 输出前加上的 <think> 推理块或寒暄废话。
    使用非贪婪正则直接刮取最外层的 { ... } 或 [ ... ]。
    """
    if not text:
        return None
        
    text = text.strip()
    
    # 手动剔除带有闭合标签的 <think>...</think> 块，防止其内部恰好有不完整的 JSON 打扰提取
    # (?s) 表示 re.DOTALL (让 . 能匹配换行符)
    text = re.sub(r'(?s)<think>.*?</think>', '', text).strip()
    
    try:
        # 1. 优先尝试直接完整解析
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[Service] {func_name}: 直接解析失败，尝试剥离 Markdown 提取 JSON...")
        pass

    # 2. 尝试提取带有 markdown block 的 JSON
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            print(f"[Service] {func_name}: Markdown 块解析失败。")

    # 3. 终极暴力正则匹配：寻找最先出现的外层 {...} 或 [...]
    # 这里我们分别找最长的 {} 和 [] 组合，看谁更像合法的 JSON
    dict_match = re.search(r'(?s)(\{.*\})', text)
    list_match = re.search(r'(?s)(\[.*\])', text)
    
    candidates = []
    if dict_match: candidates.append(dict_match.group(1).strip())
    if list_match: candidates.append(list_match.group(1).strip())
    
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
            
    print(f"[Service] {func_name}: 所有尝试均失败，无法从返回内容中提取有效 JSON。\n片段: {text[:100]}")
    return None


# =====================================================================
# 多模态 OCR 服务 - 用于扫描件识别
# =====================================================================

def ocr_with_multimodal_api(image_path: str) -> str:
    """
    调用多模态大模型 API 对扫描件图片进行 OCR。

    Args:
        image_path: 扫描件页面图片的本地路径。

    Returns:
        str: OCR 识别出的文本内容。
    """
    print(f"[Service] ocr_with_multimodal_api: 正在 OCR 识别 '{image_path}'")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    client = OpenAI(
        api_key=config.MULTIMODAL_API_KEY,
        base_url=config.MULTIMODAL_API_BASE,
    )

    response = client.chat.completions.create(
        model=config.MULTIMODAL_MODEL_NAME,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个专业的 OCR 文字识别助手。"
                    "请精确识别图片中的所有文字内容，"
                    "保持原文的段落结构和格式。"
                    "如果包含表格，请用 Markdown 表格格式输出。"
                    "如果包含公式，请用 LaTeX 格式输出。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "请识别并提取这张学术论文页面中的所有文字内容。",
                    },
                ],
            },
        ],
    )
    return response.choices[0].message.content


# =====================================================================
# DeepSeek 服务 - AI 推荐题目
# =====================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_recommend_title(
    subject: str,
    user_intent: str,
) -> list:
    """
    调用 DeepSeek 根据科目和写作方向推荐 3-5 个候选题目。

    Args:
        subject: 论文科目。
        user_intent: 用户的写作方向/意图描述。

    Returns:
        list: 推荐的题目列表。
    """
    print(f"[Service] call_deepseek_recommend_title: "
          f"科目={subject}, 方向={user_intent[:30]}...")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    system_prompt = (
        "你是一位资深学术论文选题顾问。请根据用户提供的科目和写作方向，"
        "推荐 5 个合适的论文题目。\n"
        "要求：\n"
        "1. 题目长度 5-50 字\n"
        "2. 符合学术规范\n"
        "3. 具体且有研究价值\n"
        '以 JSON 格式返回: {"titles": ["题目1", "题目2", ...]}'
    )

    user_message = f"科目: {subject}\n写作方向: {user_intent}"

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=config.DEEPSEEK_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    result_text = response.choices[0].message.content
    data = _extract_json_from_text(result_text, "call_deepseek_recommend_title")
    if data and isinstance(data, dict):
        return data.get("titles", [])
    elif data and isinstance(data, list):
        return data
    return []

# =====================================================================
# DeepSeek 服务 - AI 提取参考文献 (Phase 7 新增)
# =====================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_references_from_text(pdf_text: str) -> list:
    """
    专门调用大模型提取扫描出的 PDF 文本末尾的参考文献列表。
    为节省 Token 并提高精度，只截取文本的最后一部分进行提炼。
    """
    # 参考文献通常在最后，截取最后 8000 个字符
    tail_text = pdf_text[-8000:] if len(pdf_text) > 8000 else pdf_text

    print(f"[Service] extract_references_from_text: 正在分析文档尾部提取参考文献...")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    system_prompt = (
        "你是一个专业的学术文本提取器。你的任务是从用户提供的论文尾部文本中，"
        "精准剥离出所有的「参考文献 (References / Bibliography)」条目。\n"
        "请将提取结果严格输出为 JSON 数组格式，不要包含任何额外的 Markdown 代码块界定符或解释语。\n"
        "每个对象包含以下字段：\n"
        "- \"text\": 完整的单条参考文献文本（如 'P. Abbeel, A. Coates, and A. Y. Ng. Autonomous...'）\n"
        "\n"
        "如果没有找到任何参考文献，请输出空数组 `[]`。"
    )

    user_message = f"请提取以下文本中的参考文献：\n\n{tail_text}"

    response = client.chat.completions.create(
        model=config.MODEL_REASONING,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"} if "deepseek" not in config.MODEL_REASONING.lower() else None # DeepSeek 官方暂未完全兼容全局 json_object, 依赖 prompt
    )

    result_text = response.choices[0].message.content
    data = _extract_json_from_text(result_text, "extract_references_from_text")

    if not data:
        return []

    # 兼容处理如果是 {"references": [...]} 或 直接是 [...]
    refs_list = data if isinstance(data, list) else data.get("references", data.get("References", []))
    
    # 格式化加上 ID
    formatted_refs = []
    for i, ref in enumerate(refs_list):
        text_val = ref.get("text", str(ref)) if isinstance(ref, dict) else str(ref)
        if len(text_val) > 10: # 剔除过短的异常条目
            formatted_refs.append({
                "id": f"ref_{i:03d}",
                "text": text_val.strip()
            })
    print(f"[Service] 成功提取到 {len(formatted_refs)} 条参考文献。")
    return formatted_refs

# =====================================================================
# DeepSeek 服务 - AI 生成关键词
# =====================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_generate_keywords(
    title: str,
    subject: str,
    user_intent: str,
) -> dict:
    """
    调用 DeepSeek 根据题目和方向生成中英文关键词。

    Args:
        title: 论文题目。
        subject: 论文科目。
        user_intent: 用户的写作方向/意图描述。

    Returns:
        dict: {"cn": ["关键词1", ...], "en": ["keyword1", ...]}
    """
    print(f"[Service] call_deepseek_generate_keywords: "
          f"题目={title[:30]}...")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    system_prompt = (
        "你是一位学术论文关键词提取专家。请根据论文题目、科目和写作方向，"
        "生成 4 个中文关键词和 4 个对应的英文关键词。\n"
        "要求关键词精准、专业，能够覆盖论文的核心研究内容。\n"
        '以 JSON 格式返回: {"cn": ["关键词1", "关键词2", "关键词3", "关键词4"], '
        '"en": ["keyword1", "keyword2", "keyword3", "keyword4"]}'
    )

    user_message = (
        f"论文题目: {title}\n"
        f"科目: {subject}\n"
        f"写作方向: {user_intent}"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=config.DEEPSEEK_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    result_text = response.choices[0].message.content
    data = _extract_json_from_text(result_text, "call_deepseek_generate_keywords")
    if data and isinstance(data, dict):
        return {
            "cn": data.get("cn", [])[:4],
            "en": data.get("en", [])[:4],
        }
    return {"cn": [], "en": []}


# =====================================================================
# DeepSeek 服务 - 对抗式大纲生成 (骨架 + 双变体)
# =====================================================================

def _build_config_context(paper_config: dict) -> str:
    """构建论文配置上下文字符串（内部复用）。"""
    if not paper_config:
        return ""
    return (
        f"\n\n论文配置信息：\n"
        f"- 科目: {paper_config.get('paper_subject', '未指定')}\n"
        f"- 题目: {paper_config.get('paper_title', '未指定')}\n"
        f"- 语言: {paper_config.get('paper_language', '中文')}\n"
        f"- 学业类型: {paper_config.get('academic_type', '本科')}\n"
        f"- 论文水平: {paper_config.get('paper_level', '初级')}\n"
        f"- 论文类型: {paper_config.get('paper_type', '毕业论文')}\n"
        f"- 目标字数: {paper_config.get('target_word_count', 8000)}\n"
        f"- 中文关键词: {', '.join(paper_config.get('keywords_cn', []))}\n"
        f"- 英文关键词: {', '.join(paper_config.get('keywords_en', []))}\n"
    )


def _parse_json_response(result_text: str, func_name: str) -> dict:
    """包装一下通用的 _extract_json_from_text，返回骨架所需的 dict。"""
    data = _extract_json_from_text(result_text, func_name)
    if isinstance(data, dict):
        return data
    print(f"[Service] {func_name}: 提取的结果不是字典类型，返回空 {{}}")
    return {}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_generate_skeleton(
    pdf_text: str,
    user_intent: str,
    paper_config: dict = None,
) -> dict:
    """
    调用 DeepSeek 生成大纲骨架（仅章节标题，不含要点）。

    Returns:
        dict: {"title": "...", "sections": [{"heading": "..."}, ...]}
    """
    print(f"[Service] call_deepseek_generate_skeleton: "
          f"生成骨架 (意图: {user_intent[:30]}...)")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    config_context = _build_config_context(paper_config)

    system_prompt = (
        "你是一位资深学术论文写作顾问。请根据以下论文素材和用户的写作方向，"
        "生成一份论文大纲的 **章节框架**（仅包含论文标题和各章节标题，"
        "不要生成具体要点）。\n"
        "JSON 格式要求: "
        '{"title": "论文标题", '
        '"sections": [{"heading": "第一章 引言"}, {"heading": "第二章 ..."}, ...]}'
        "\n\n注意：\n"
        "1. 章节数量应符合论文类型和学业水平要求\n"
        "2. 章节标题应清晰、规范、有逻辑递进关系\n"
        "3. 只返回框架，不要生成任何要点或子标题"
        + config_context
    )

    user_message = (
        f"## 论文素材\n{pdf_text[:config.MAX_TEXT_CONTEXT_CHARS]}\n\n"
        f"## 写作方向\n{user_intent}"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    return _parse_json_response(
        response.choices[0].message.content,
        "call_deepseek_generate_skeleton",
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_fill_variant_a(
    skeleton: dict,
    pdf_text: str,
    user_intent: str,
    paper_config: dict = None,
) -> dict:
    """
    基于骨架生成大纲变体 A（严谨学术风格，temperature=0.5）。

    Returns:
        dict: {"title": "...", "sections": [{"heading": "...", "points": [...]}]}
    """
    print("[Service] call_deepseek_fill_variant_a: 生成变体 A（严谨学术）")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    config_context = _build_config_context(paper_config)
    skeleton_json = json.dumps(skeleton, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是一位 **顶尖高校的严谨学术导师**，擅长经典理论框架和规范性论述。\n"
        "请基于以下大纲骨架，为每个章节填充 4-6 个具体、深入的要点（points）。\n\n"
        "你的风格特点与要求：\n"
        "- **理论深度**：重视经典理论和既有研究梳理，不要泛泛而谈，必须有专业术语的支撑。\n"
        "- **逻辑严密**：强调方法论的严谨性和可重复性，要点之间必须有强烈的因果或递进逻辑。\n"
        "- **规范性优先**：以系统性和规范性为先，避免情绪化或主观随意的表达。\n"
        "- **内容详实**：每个要点应是一句完整、信息密集的核心句，而不仅仅是两三个字的短语。\n\n"
        "JSON 格式要求: "
        '{"title": "论文标题", '
        '"sections": [{"heading": "章节标题", "points": ["要点1", "要点2", ...]}]}\n\n'
        "重要：必须严格遵循给定的章节框架，不要增删章节，只填充要点。"
        + config_context
    )

    user_message = (
        f"## 大纲骨架\n{skeleton_json}\n\n"
        f"## 论文素材\n{pdf_text[:config.MAX_TEXT_CONTEXT_CHARS]}\n\n"
        f"## 写作方向\n{user_intent}"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    return _parse_json_response(
        response.choices[0].message.content,
        "call_deepseek_fill_variant_a",
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_fill_variant_b(
    skeleton: dict,
    pdf_text: str,
    user_intent: str,
    paper_config: dict = None,
) -> dict:
    """
    基于骨架生成大纲变体 B（创新发散风格，temperature=0.9）。

    Returns:
        dict: {"title": "...", "sections": [{"heading": "...", "points": [...]}]}
    """
    print("[Service] call_deepseek_fill_variant_b: 生成变体 B（创新发散）")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    config_context = _build_config_context(paper_config)
    skeleton_json = json.dumps(skeleton, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是一位 **顶尖科研机构的创新型研究员**，擅长跨学科思维和前沿视角。\n"
        "请基于以下大纲骨架，为每个章节填充 4-6 个具体、深入的要点（points）。\n\n"
        "你的风格特点与要求：\n"
        "- **视角新颖**：善于从新颖的切入点剖析常规问题，提出具有启发性的假说。\n"
        "- **前沿交叉**：注重跨学科交叉与最新的技术趋势，引用前沿概念。\n"
        "- **实践导向**：强调实践应用和创新落地价值，不拘泥于陈旧理论。\n"
        "- **内容详实**：每个要点应是一句完整、信息密集的核心论述句，而不仅仅是几个字的短语。\n\n"
        "JSON 格式要求: "
        '{"title": "论文标题", '
        '"sections": [{"heading": "章节标题", "points": ["要点1", "要点2", ...]}]}\n\n'
        "重要：必须严格遵循给定的章节框架，不要增删章节，只填充要点。"
        + config_context
    )

    user_message = (
        f"## 大纲骨架\n{skeleton_json}\n\n"
        f"## 论文素材\n{pdf_text[:config.MAX_TEXT_CONTEXT_CHARS]}\n\n"
        f"## 写作方向\n{user_intent}"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    return _parse_json_response(
        response.choices[0].message.content,
        "call_deepseek_fill_variant_b",
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_review_outline(outline: dict) -> str:
    """
    调用 DeepSeek 审阅并优化大纲，返回审阅意见。

    Args:
        outline: 待审阅的结构化大纲。

    Returns:
        str: 审阅意见和优化建议。
    """
    print("[Service] call_deepseek_review_outline: 审阅大纲")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    system_prompt = (
        "你是一位经验丰富的学术论文审稿人。请审阅以下论文大纲，"
        "从结构完整性、逻辑连贯性、学术规范性等角度给出详细的修改建议。"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=config.DEEPSEEK_TEMPERATURE,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(outline, ensure_ascii=False)},
        ],
    )
    return response.choices[0].message.content


# =====================================================================
# DeepSeek 服务 - 用于分章节写作
# =====================================================================

def _get_chapter_context(heading: str, points: list, full_text: str, vector_store=None) -> str:
    """
    为当前章节获取最佳参考素材上下文。
    
    如果提供了 vector_store (FAISS)，则使用语义检索获取 Top K 最相关的片段。
    否则回退到传统的全文截断模式。
    
    Args:
        heading: 当前章节标题。
        points: 当前章节要点列表。
        full_text: 完整的 PDF 解析文本（回退用）。
        vector_store: FAISS 向量库实例（可选）。
        
    Returns:
        str: 拼接好的上下文字符串。
    """
    if vector_store is not None:
        try:
            # 用章节标题 + 要点组合成检索 Query
            query = heading + " " + " ".join(points[:6])
            retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            retrieved_docs = retriever.invoke(query)
            
            rag_context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
            print(f"[RAG] 章节 '{heading}' 检索到 {len(retrieved_docs)} 个相关片段 "
                  f"(共 {len(rag_context)} 字)")
            return rag_context
        except Exception as e:
            print(f"[RAG] 检索失败，回退到截断模式: {e}")
    
    # 回退：传统截断
    print(f"[Service] 使用传统截断模式 (前 {config.MAX_TEXT_CONTEXT_CHARS} 字)")
    return full_text[:config.MAX_TEXT_CONTEXT_CHARS]


def _get_chapter_images(
    heading: str,
    points: list,
    vector_store,
    all_images: list,
    k: int = 3,
) -> list:
    """
    利用 FAISS 向量库按章节语义检索最相关的图片。
    
    原理：图片的 rich_context 已作为带 metadata={"type":"image"} 的文档
    嵌入 FAISS。用章节标题+要点作为 Query 查询，筛选出 image 类型的
    结果，返回最相关的 Top K 张图片。
    
    Args:
        heading: 当前章节标题。
        points: 当前章节要点列表。
        vector_store: FAISS 向量库实例（如果为 None 则回退到全量）。
        all_images: 全部可用图片列表。
        k: 最多返回多少张图片。
        
    Returns:
        list: 与该章节语义最相关的图片信息列表。
    """
    if vector_store is None or not all_images:
        # 回退到全局模式
        return all_images
    
    try:
        # 用章节标题 + 要点组合成检索 Query
        query = heading + " " + " ".join(points[:6])
        
        # 检索更多结果（因为大部分是文本 Chunk，图片占少数）
        retriever = vector_store.as_retriever(search_kwargs={"k": 20})
        retrieved_docs = retriever.invoke(query)
        
        # 筛选出 image 类型的文档
        matched_image_ids = []
        for doc in retrieved_docs:
            if doc.metadata.get("type") == "image":
                img_id = doc.metadata.get("image_id")
                if img_id and img_id not in matched_image_ids:
                    matched_image_ids.append(img_id)
                    if len(matched_image_ids) >= k:
                        break
        
        if matched_image_ids:
            # 按检索到的 ID 从全量图片中取出完整图片信息
            img_dict = {img["id"]: img for img in all_images}
            chapter_images = [img_dict[iid] for iid in matched_image_ids if iid in img_dict]
            
            print(f"[RAG] 章节 '{heading}' 检索到 {len(chapter_images)} 张相关图片: "
                  f"{[img['id'] for img in chapter_images]}")
            return chapter_images
        else:
            print(f"[RAG] 章节 '{heading}' 未检索到相关图片，不分发图片")
            return []
            
    except Exception as e:
        print(f"[RAG] 图片检索失败, 回退到全局模式: {e}")
        return all_images


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_deepseek_write_chapter(
    heading: str,
    points: list,
    context: str,
    full_outline: dict,
    images_data: list = None,
    references_data: list = None,
    vector_store = None,
    paper_config: dict = None,
) -> str:
    """
    调用 DeepSeek 为单个章节生成正文内容。

    Args:
        heading: 章节标题 (如 "1. 引言")。
        points: 章节要点列表。
        context: 参考论文的相关文本上下文。
        full_outline: 完整的论文大纲（用于保持全局连贯性）。
        images_data: 提取到的原生图片信息及字典，供 AI 参考插入。
        paper_config: 论文配置 (语言、学业类型、水平等)。

    Returns:
        str: 该章节的正文 Markdown 文本。
    """
    print(f"[Service] call_deepseek_write_chapter: "
          f"撰写章节 '{heading}' (要点: {len(points)} 个)")

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_BASE,
    )

    image_descriptions = "无"
    if images_data:
        image_descriptions = ""
        for img in images_data:
            # 去除过度冗杂的“第X页”等来源信息，只保留精华图片描述给 AI
            context_hint = img.get('rich_context', img.get('caption_context', '无'))
            image_descriptions += f"- 图片ID: {img.get('id', 'unknown')}\n  详细图注与全文语义上下文: {context_hint}\n"
            
    reference_descriptions = "无"
    if references_data:
        reference_descriptions = ""
        for ref in references_data:
            reference_descriptions += f"- 文献ID: {ref.get('id', 'unknown')}\n  文献详情: {ref.get('text', '无')}\n"

    # 根据论文配置调整写作指导
    level_guidance = ""
    if paper_config:
        lang = paper_config.get('paper_language', '中文')
        level = paper_config.get('paper_level', '初级')
        academic = paper_config.get('academic_type', '本科')
        word_count = paper_config.get('target_word_count', 8000)
        sections_count = len(full_outline.get('sections', []))
        words_per_section = word_count // max(sections_count, 1)

        level_guidance = (
            f"\n7. 使用{lang}撰写\n"
            f"8. 写作水平要求：{academic}{level}级别\n"
            f"9. 本章节目标字数约 {words_per_section} 字\n"
        )

    system_prompt = (
        "你是一位在国际顶级学术期刊发表过多篇论文的资深撰写专家。请严格按照给定的章节大纲与要点，"
        "撰写该章节的正式文本。请务必遵守以下至高准则：\n\n"
        "1. **学术黑话与专业语气**：绝不可使用口语、博客体或自媒体口吻。必须使用高度书面化、客观、规范的中/英语术语表述。避免第一人称（如“我们发现”、“我认为”），改用被动语态或客观陈述（如“研究表明”、“数据证实”）。\n"
        "2. **饱满的段落结构**：切忌记流水账。每个设定的「要点」必须展开为一个或多个层次分明的段落。每段应包含【论点 (Topic Sentence)】、【论据展开 (Elaboration)】和【小结过渡 (Transition)】。单章字数务必充足，做到言之有物，严禁空话套话重复。\n"
        "3. **紧扣参考素材**：尽可能汲取并转述「参考素材」中的具体数据、案例、机制或公式，不要单纯依赖大模型自身的预训练知识进行发散。\n"
        "4. **文献引用规范**：在文中陈述他人观点、引出前人模型或使用数据时，必须极其自然地插入引用标记。你**必须**使用「可用参考文献列表」中的文献。引用时，**必须且只能**输出占位符标记：`[REF_文献ID]`，例如 `[REF_ref_001]` 或 `[REF_001]`。系统随后会自动为你排序并替换成上标 `[1]`。**绝不可**自行输出普通的 `[1]` 或 `(Author, Year)` 格式！如果本章探讨了经典算法或综述内容，**强制要求你至少引用 1-3 篇相关的文献**！如果完全不引用文献，将被视为严重的学术失职。\n"
        "5. **高级 LaTeX 排版**：如果涉及数学表达式、物理量、变量字母（如 x, y, α），无论是独立公式还是行内变量，**必须**使用 LaTeX 格式输出（例如独立公式使用 `$$ E=mc^2 $$`，行内形式使用 `$_t$`，**注意行内公式内部边缘绝不可有空格！！！写成 `$_t$` 而绝不能是 `$ _t $`**）。如果原文素材中有公式，在此处引用时务必原样或优化后呈现。\n"
        "6. **Markdown 结构编排与格式限制**：直接输出正文，不要输出标题（系统已自带）。可根据需要合理使用 Markdown 次级标题（`###`）或加粗列表来优化该章内部的可读性。**绝对禁止在正文段落中使用 `**加粗**` 语法突出显示词汇或句子**，统一保持平实字体。\n"
        "7. **严格呼应上下文**：充分阅读给定的《完整论文大纲》，确保你写的这一章在这个系统内承上启下，绝不可以跑题或涵盖属于其他章节的内容。\n"
        "8. **智能插图引擎**：如果你认为该章节当前讲述的内容可以通过「可用图片资源列表」中的某张图片进行更直观的展示印证，请**必须**在段落之间的独立一行输出占位符标记：[INSERT_IMG_{图片ID}]，例如 [INSERT_IMG_img_001]。**确保占位符独立占一行，且不要被反引号包围！**\n"
        "   - 系统随后会在该位置自动插入这幅图（不需要你自己写图注）。\n"
        "   - 切勿生造未出现在列表中的图片ID。如果你在这章不需要配图，完全可以不使用任何占位符。\n"
        "   - 在正文提到此图时，可以用类似“如图所示（见所附图表）”、“该模型结构如下”等通用学术术语进行引导。\n"
        + level_guidance
    )

    user_message = (
        f"## 完整论文大纲\n"
        f"{json.dumps(full_outline, ensure_ascii=False, indent=2)}\n\n"
        f"## 当前需要撰写的章节\n"
        f"**标题**: {heading}\n"
        f"**要点**: {json.dumps(points, ensure_ascii=False)}\n\n"
        f"## 可用图片资源列表\n"
        f"{image_descriptions}\n\n"
        f"## 可用参考文献列表\n"
        f"{reference_descriptions}\n\n"
        f"## 参考素材\n{_get_chapter_context(heading, points, context, vector_store)}"
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL_NAME,
        temperature=config.DEEPSEEK_TEMPERATURE,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content
