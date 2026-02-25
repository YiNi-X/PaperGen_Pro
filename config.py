"""
PaperGen_Pro - 全局配置模块

集中管理模型名称、温度参数、API Base URL 等配置。
所有 API Key 从环境变量中获取。
"""
import os

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ===== API Keys =====
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ===== Kimi (Moonshot) 配置 - 用于多模态 OCR =====
KIMI_API_BASE = "https://api.moonshot.cn/v1"
KIMI_MODEL_NAME = "moonshot-v1-128k"
KIMI_TEMPERATURE = 0.3

# ===== DeepSeek 配置 - 用于论文写作 =====
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_TEMPERATURE = 0.7

# ===== 多模态 API 配置 - 用于全页 OCR =====
MULTIMODAL_API_BASE = "https://api.moonshot.cn/v1"
MULTIMODAL_MODEL_NAME = "kimi-k2.5"
MULTIMODAL_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")

# ===== PDF 解析配置 =====
MAX_PDF_SIZE_MB = 50
MAX_UPLOAD_FILES = 5
MIN_IMAGE_WIDTH = 100   # 像素，过滤过小的装饰图
MIN_IMAGE_HEIGHT = 100
CAPTION_CONTEXT_CHARS = 300  # 图片前后截取的字符数
SCANNED_TEXT_THRESHOLD = 50  # 首页文字少于此值判定为扫描件（V3废弃判断，统一走全面OCR）
MAX_WORKERS = 5              # 多页并发 OCR 的线程数

# ===== 临时文件目录 =====
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
TEMP_FIGURES_DIR = os.path.join(TEMP_DIR, "figures")
TEMP_OUTPUT_DIR = os.path.join(TEMP_DIR, "output")

# ===== 通用配置 =====
DEFAULT_LANGUAGE = "zh-CN"
MAX_TEXT_CONTEXT_CHARS = 100000  # 限制传入 LLM 的最大字符数 (约4-5万Token)，防崩溃与截断幻觉
