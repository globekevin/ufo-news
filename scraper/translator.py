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
TRANSLATION_SYSTEM_PROMPT = """你是一位专业的 UFO/UAP 领域新闻翻译专家。请将以下英文新闻标题和导语翻译成中文。

要求：
1. 标题翻译要简洁有力，保留原文的信息量和冲击力
2. 导语翻译要流畅自然，符合中文阅读习惯
3. 专业术语保持准确（如 UAP=不明空中现象, UFO=不明飞行物, Pentagon=五角大楼, whistleblower=吹哨人/举报人, congressional hearing=国会听证会, disclosure=披露）
4. 人名、地名、机构名保留英文原名并用括号注明中文
5. 如果原文是美国政府/军方相关的内容，保持严肃客观的语调
6. 如果原文是目击报告类，可以适当生动但不过度渲染

只输出 JSON 格式，不要输出其他内容：
[{"title": "原文标题", "title_cn": "中文标题", "summary": "原文导语", "summary_cn": "中文导语"}]"""


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
        items.append({
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
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
