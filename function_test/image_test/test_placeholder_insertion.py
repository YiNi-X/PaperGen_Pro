import re
import os
from openai import OpenAI
from dotenv import load_dotenv

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_ROOT, ".env"))

# Fake configuration for testing purposes
class Config:
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = "https://api.deepseek.com"
    MULTIMODAL_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
    MULTIMODAL_API_BASE = "https://api.moonshot.cn/v1"

config = Config()

def mock_call_ai_writer(context_text: str, available_images: list) -> str:
    """Mocks the AI chapter writing process with image injection placeholders."""
    if not config.DEEPSEEK_API_KEY:
        print("Set DEEPSEEK_API_KEY environment variable.")
        return ""
        
    client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_API_BASE)
    
    # Format image metadata for the AI
    image_descriptions = "可用图片资源列表：\n"
    for img in available_images:
        image_descriptions += f"- 图片ID: {img['id']}\n  上下文: {img['context']}\n"
    
    system_prompt = (
        "你是一个专业的学术论文写手。\n"
        "你的任务是根据提供的参考文本和可用图片资源，撰写一段连贯的学术正文。\n"
        "【重要指令 - 图片插入】：\n"
        "如果你在行文中需要引用或展示某张「可用图片资源」中的图，请在段落之间另起一行，"
        "并严格使用占位符格式：`[INSERT_IMG_{图片ID}]`，例如 `[INSERT_IMG_img_001]`。\n"
        "每次插入图片后，需要在下一行用简短的文字作为该图的图注（说明）。\n"
        "请勿捏造列表中不存在的图片ID。"
    )
    
    user_prompt = f"参考文本：\n{context_text}\n\n{image_descriptions}\n\n请开始撰写正文片断："
    
    print("Calling AI writer...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling DeepSeek: {e}")
        return ""

def resolve_placeholders(ai_generated_text: str, available_images: list) -> list:
    """
    Parses the AI output to separate text blocks and image placeholders.
    Returns a list of elements: [{"type": "text", "content": "..."}, {"type": "image", "path": "..."}]
    """
    elements = []
    
    # Regex to match [INSERT_IMG_xxx] exactly on its own line or within text
    pattern = r'\[INSERT_IMG_([^\]]+)\]'
    
    # Split the text based on the regex matches
    parts = re.split(pattern, ai_generated_text)
    
    # Mapping dict for easy lookup
    img_dict = {img["id"]: img for img in available_images}
    
    for i, part in enumerate(parts):
        # Even indices are normal text, odd indices are regex capture groups (image IDs)
        if i % 2 == 0:
            text_content = part.strip()
            if text_content:
                elements.append({"type": "text", "content": text_content})
        else:
            img_id = part.strip()
            if img_id in img_dict:
                elements.append({
                    "type": "image",
                    "id": img_id,
                    "path": img_dict[img_id]["path"],
                    "context": img_dict[img_id]["context"]
                })
            else:
                print(f"Warning: AI generated a placeholder for unknown image ID '{img_id}'")
                
    return elements

if __name__ == "__main__":
    # 模拟数据
    sample_context = "近年来，深度学习在图像识别方面取得了显著进展。ResNet架构通过引入残差连接，成功训练了上百层的神经网络，极大地降低了错误率。"
    sample_images = [
        {"id": "img_001", "path": "temp/figures/resnet_arch.png", "context": "图1：ResNet残差块结构解析"},
        {"id": "img_002", "path": "temp/figures/error_rate.png", "context": "表1：不同网络层数在ImageNet上的错误率对比"}
    ]
    
    print("--- 步骤 1: 模拟 AI 撰写正文并打标记 ---")
    ai_text = mock_call_ai_writer(sample_context, sample_images)
    print("\n【AI 生成的原始内容】:\n")
    print(ai_text)
    print("\n" + "="*50 + "\n")
    
    print("--- 步骤 2: 正则解析，转变为排版对象队列 ---")
    parsed_elements = resolve_placeholders(ai_text, sample_images)
    for index, elem in enumerate(parsed_elements):
        if elem["type"] == "text":
            print(f"[{index}] TEXT BLOCK (len {len(elem['content'])}):\n{elem['content'][:100]}...\n")
        elif elem["type"] == "image":
            print(f"[{index}] IMAGE BLOCK: ID={elem['id']}, Path='{elem['path']}', Context='{elem['context']}'\n")
