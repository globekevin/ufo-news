"""
DeepSeek 翻译模块。
使用 DeepSeek Chat API 将英文 UFO 新闻标题和导语翻译成中文。
"""

import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# 翻译提示词模板
TRANSLATION_SYSTEM_PROMPT = """你是一位专业的 UFO/UAP 领域新闻翻译与编辑专家。请处理以下英文新闻。

**核心任务：为每条新闻生成中文新闻正文（body_cn）。** 规则如下：

1. **如果提供了英文正文（body 字段有内容）**：直接翻译成流畅的中文新闻正文。保持原文信息量和叙事结构，段落自然分段。不要添加原文没有的信息。

2. **如果只提供了标题（body 字段为空或很短）**：基于标题和导语，撰写一段 100-200 字的中文新闻正文。保持客观新闻语调，不要虚构细节，可以从 UFO/UAP 领域的常识角度补充简要背景。目的是让读者在详情页看到一段像样的新闻正文，而不是只有一句话。

**其他翻译要求：**
- title_cn：标题翻译要简洁有力，保留原文的信息量和冲击力
- summary_cn：导语翻译，1-2 句话，流畅自然
- body_cn：新闻正文。如果原文有 body 就翻译，没有就基于标题扩写。
- 绝不翻译配图说明（如 "A photo of..."、"Image credit:"、"©"）、作者署名、发布日期、分享按钮等非正文内容
- 专业术语：UAP=不明空中现象, UFO=不明飞行物, Pentagon=五角大楼, FOIA=信息自由法, witness=目击者, nuke=核设施, pilot=飞行员
- 人名地名机构名保留英文原名并括号注明中文
- 美国政府/军方内容保持严肃客观；目击报告可适当生动但不渲染

只输出 JSON，格式如下：
[{"title": "…", "title_cn": "…", "summary": "…", "summary_cn": "…", "body_cn": "…"}]"""


def _call_deepseek(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """调用 DeepSeek Chat API"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    resp = requests.post(
        DEEPSEEK_API_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def translate_articles(articles: list[dict], api_key: str = "") -> list[dict]:
    """
    批量翻译文章标题和导语。

    参数:
        articles: 待翻译的文章列表（每个 dict 含 title, summary 字段）
        api_key: DeepSeek API 密钥

    返回:
        添加了 title_cn 和 summary_cn 字段的文章列表
    """
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        logger.error("DEEPSEEK_API_KEY not set. Skipping translation.")
        # 降级：用原标题作为中文标题
        for a in articles:
            a["title_cn"] = f"[原文] {a.get('title', '')}"
            a["summary_cn"] = a.get("summary", "")
        return articles

    # 构建翻译请求 —— 一次翻译 6 条，节省 API 调用
    items = []
    for a in articles:
        body = a.get("body", "")[:2000]  # 正文截取前 2000 字符
        has_body = len(body) > 60  # 是否有足够的原文正文
        items.append({
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
            "body": body if has_body else "(仅有标题，请基于标题和导语扩展中文正文)",
            "has_body": has_body,
        })

    user_prompt = json.dumps(items, ensure_ascii=False)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = _call_deepseek(TRANSLATION_SYSTEM_PROMPT, user_prompt, api_key)

            # 解析 JSON 结果
            # 处理可能的 markdown code block 包裹
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1])

            translated = json.loads(result)

            # 合并翻译结果
            for i, t in enumerate(translated):
                if i < len(articles):
                    articles[i]["title_cn"] = t.get("title_cn", articles[i].get("title", ""))
                    articles[i]["summary_cn"] = t.get("summary_cn", articles[i].get("summary", ""))
                    articles[i]["body_cn"] = t.get("body_cn", articles[i].get("body", ""))

            logger.info(f"Translated {len(translated)} articles via DeepSeek")
            return articles

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
            logger.debug(f"Raw response: {result[:500]}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except requests.RequestException as e:
            logger.error(f"DeepSeek API error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                # 最终降级
                for a in articles:
                    a["title_cn"] = f"[API错误] {a.get('title', '')}"
                    a["summary_cn"] = a.get("summary", "")
                break

    return articles
