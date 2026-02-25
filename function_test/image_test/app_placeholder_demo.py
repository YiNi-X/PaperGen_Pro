import os
import re
import streamlit as st

st.set_page_config(page_title="插图排版架构对比演示", layout="wide")

# ==========================================
# 模拟的数据源 (Mock Data)
# ==========================================
MOCK_IMAGES = {
    "img_001": {
        "url": "https://images.unsplash.com/photo-1555949963-aa79dcee981c?w=600&q=80",
        "context": "图1：深度学习模型架构图（示意）",
        "caption": "图1：残差网络结构"
    },
    "img_002": {
        "url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&q=80",
        "context": "表1：不同模型在数据集上的准确率对比表格",
        "caption": "表1：准确率对比数据"
    }
}

OLD_WAY_TEXT = """\
深度学习在计算机视觉领域取得了巨大成功。传统的卷积神经网络随着层数的加深，会出现梯度消失的问题。
何恺明等人提出了残差网络（ResNet），通过引入跳跃连接（Skip Connection）解决了这一难题，使得训练上百层的网络成为可能。

在 ImageNet 数据集上的测试表明，ResNet-152 的错误率远低于之前的 VGG 和 GoogLeNet 等模型。
具体的数据表明，随着深度的增加，模型的表征能力确实得到了质的飞跃。

（旧版逻辑：发现关键词“准确率”、“结构”，在段落结束或文章末尾强行插入所有相关的图片，导致图文割裂。）
"""

NEW_WAY_AI_RESPONSE = """\
深度学习在计算机视觉领域取得了巨大成功。传统的卷积神经网络随着层数的加深，会出现梯度消失的问题。
何恺明等人提出了残差网络（ResNet），通过引入跳跃连接（Skip Connection）解决了这一难题，使得训练上百层的网络成为可能。其具体的网络架构如下所示：

[INSERT_IMG_img_001]
图1：深度学习模型架构图（示意）

在 ImageNet 数据集上的测试表明，ResNet-152 的错误率远低于之前的 VGG 和 GoogLeNet 等模型。研究人员整理了不同深度的网络在验证集上的表现：

[INSERT_IMG_img_002]
表1：不同模型在数据集上的准确率对比表格

如上表的数据表明，随着深度的增加，模型的表征能力确实得到了质的飞跃，并且由于残差块的存在并没有出现严重的退化现象。
"""

# ==========================================
# 渲染函数
# ==========================================

def render_old_way():
    st.subheader("❌ 旧版架构：关键字硬插入 / 文末堆砌")
    st.markdown("这是现有系统最常见的生成结果：图片往往在文字讲完之后，甚至是段落毫不相干的地方被生硬地贴拢在一起。")
    
    with st.container(border=True):
        st.markdown("#### 正文内容")
        st.write(OLD_WAY_TEXT)
        
        st.markdown("---")
        st.markdown("#### 附加插图 (由于找不到极其精确的锚点，通常在段末或文末统一堆砌)")
        cols = st.columns(2)
        with cols[0]:
            st.image(MOCK_IMAGES["img_001"]["url"], caption=MOCK_IMAGES["img_001"]["caption"])
        with cols[1]:
            st.image(MOCK_IMAGES["img_002"]["url"], caption=MOCK_IMAGES["img_002"]["caption"])

def render_new_way():
    st.subheader("✅ 新版架构 (Phase 5)：AI 占位符精准控制")
    st.markdown("AI 像真正的人类作者一样，在行文中根据上下文**自主决定**在哪里放图，并留下 `[INSERT_IMG_xxx]` 标记。系统通过正则将其替换为真正的渲染组件。")
    
    with st.container(border=True):
        st.markdown("#### 正文内容与原位插图")
        
        # 核心解析逻辑 (与最终写入 python-docx 的逻辑完全一致)
        pattern = r'\[INSERT_IMG_([^\]]+)\]'
        parts = re.split(pattern, NEW_WAY_AI_RESPONSE)
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # 纯文本段落
                text_content = part.strip()
                if text_content:
                    st.write(text_content)
            else:
                # 图片占位符
                img_id = part.strip()
                if img_id in MOCK_IMAGES:
                    img_data = MOCK_IMAGES[img_id]
                    # 精准在文字中间插入图片
                    st.image(img_data["url"], caption=f"✨ {img_data['caption']} (由 AI 精准插入)", use_container_width=True)
                else:
                    st.error(f"[缺失图片资源: {img_id}]")

# ==========================================
# 界面布局
# ==========================================
st.title("👀 AI 驱动的占位符排版引擎对比演示")
st.caption("运行环境：PaperGen_Pro / function_test")

col1, col2 = st.columns(2)

with col1:
    render_old_way()
    
with col2:
    render_new_way()

st.divider()
st.markdown("""
### 💡 结论
通过对比可以非常直观地看出：
- **旧版** 的图文是分离的，系统必须通过极其复杂的文本相似度算法去“猜”图片应该放在哪，稍有不慎就会错位或者全部堆在文末（特别是一章有多张图时）。
- **新版** 利用了大语言模型极强的逻辑排版能力，赋予 AI 完整的「图片资产列表」，让 AI 像人类发公众号一样，主动用代码标签 `[INSERT_IMG_xxx]` 召唤图片。后处理引擎只需简单的正则表达式即可实现图文的高级完美嵌套。
""")
