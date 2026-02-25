import sys
import os

# 确保能导入 backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from backend.services import _extract_json_from_text

test_input = """
<think>
大模型正在思考...
提取的参考文献有3条，我需要输出一个 JSON 数组。
</think>

我已经为你提取好啦，下面是结果：
```json
[
  {"text": "Smith, J. (2020). AI."},
  {"text": "Doe, A. (2021). ML."}
]
```
祝您论文写作顺利！
"""

result = _extract_json_from_text(test_input, "test_func")
print("Parsed Result:", result)
assert isinstance(result, list)
assert len(result) == 2
print("Test Passed: The new extractor successfully ignored the <think> block and conversational filler.")
