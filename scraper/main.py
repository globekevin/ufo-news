#!/usr/bin/env python3
"""
UFO 新闻聚合主脚本。
每日运行：抓取 → 精选 → 翻译 → 下载图片 → 输出 JSON。
"""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from sources import fetch_all_sources, pick_top_articles
from translator import translate_articles

# ── 配置 ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SITE_DIR = PROJECT_ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
SITE_IMG_DIR = SITE_DIR / "img"
NEWS_JSON = DATA_DIR / "news.json"
SITE_NEWS_JSON = SITE_DATA_DIR / "news.json"

MAX_ARTICLES = 6
IMAGE_MAX_WIDTH = 800
IMAGE_QUALITY = 85
IMAGE_REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ufo-scraper")


# ── 图片处理 ────────────────────────────────────────────────

def download_and_process_image(image_url: str) -> Optional[str]:
    """下载远程图片，压缩后保存。返回相对路径。"""
    if not image_url:
        return None

    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=IMAGE_REQUEST_TIMEOUT)
        resp.raise_for_status()

        img = Image.open(BytesIO(resp.content))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if img.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / img.width
            img = img.resize((IMAGE_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)

        name_hash = hashlib.md5(image_url.encode()).hexdigest()[:10]
        fname = f"{name_hash}.jpg"
        img.save(SITE_IMG_DIR / fname, "JPEG", quality=IMAGE_QUALITY, optimize=True)

        relative = f"img/{fname}"
        logger.info(f"  Image saved: {relative}")
        return relative

    except Exception as e:
        logger.warning(f"  Image failed: {e}")
        return None


# ── 数据输出 ────────────────────────────────────────────────

def save_news_json(articles_data: list[dict]) -> None:
    """保存新闻数据到 JSON 文件（双份：data/ 和 site/data/）"""
    output = {
        "updated": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "count": len(articles_data),
        "articles": articles_data,
    }

    # 保存到项目根 data/ 目录（版本控制）
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 同时保存到 site/data/ 目录（随 GitHub Pages 部署）
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SITE_NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to {NEWS_JSON} and {SITE_NEWS_JSON}")


# ── 降级内容 ────────────────────────────────────────────────

FALLBACK_ARTICLES = [
    {
        "title_cn": "五角大楼发布最新 UAP 年度报告：数百起未解事件持续追踪",
        "summary_cn": "美国国防部全域异常解析办公室（AARO）公布了年度不明异常现象报告，记录了数百起军事人员目击事件，其中多起仍无法用常规手段解释，引发新一轮国会关注。",
    },
    {
        "title_cn": "NASA UAP 独立研究小组发布最终建议：呼吁建立科学观测网络",
        "summary_cn": "NASA 任命的不明异常现象独立研究小组在最终报告中建议，应利用现有科学基础设施建立系统化 UAP 数据采集与分析框架，而非依赖零星军事报告。",
    },
    {
        "title_cn": "前空军情报官国会证词：美国政府持有「非人类」飞行器残骸",
        "summary_cn": "前空军情报官员 David Grusch 在国会听证会上宣誓作证，声称美国政府秘密运行着一个数十年的「非人类技术逆向工程」计划，已回收多具非人类生物遗骸。",
    },
    {
        "title_cn": "智利 CEFAA 机构公开最新 UFO 案例：红外摄像机捕获高速目标",
        "summary_cn": "智利民用航空局下属的异常空中现象研究委员会（CEFAA）公布了一段由军用红外摄像机拍摄的视频，显示一个高速移动且无明显推进装置的目标。",
    },
    {
        "title_cn": "哈佛天文学家 Avi Loeb：星际流星残骸回收取得初步成果",
        "summary_cn": "「伽利略计划」负责人 Avi Loeb 教授宣布，其团队在太平洋海底回收的 IM1 流星残骸中发现了异常元素比例，可能指向星际技术来源，论文已提交同行评审。",
    },
    {
        "title_cn": "英国国防部解密 UFO「X档案」最后一卷：跨越 50 年的官方记录",
        "summary_cn": "英国国家档案馆公布了国防部 UFO 档案的最终批次，涵盖 1950 年至 2009 年间收到的全部不明飞行物报告，其中包含多名警察和军事飞行员的第一手目击记录。",
    },
]


def generate_fallback() -> list[dict]:
    """生成降级内容（当数据源不可用时）"""
    articles = []
    now = datetime.now().isoformat()
    for i, item in enumerate(FALLBACK_ARTICLES, 1):
        articles.append({
            "id": f"fallback-{i}",
            "title": f"UFO News Headline #{i}",
            "url": "#",
            "summary": "",
            "image_url": "",
            "source_name": "〓 系统公告 〓",
            "published": now,
            "score": 0,
            "title_cn": item["title_cn"],
            "summary_cn": item["summary_cn"],
            "local_image": "",
        })
    logger.warning("Using fallback content — data sources unavailable")
    return articles


# ── 主流程 ──────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("🛸 UFO News Scraper — Daily Run")
    logger.info("=" * 60)

    # 1. 抓取
    logger.info("[1/4] Fetching from all sources...")
    all_articles = fetch_all_sources()

    if not all_articles:
        logger.error("Zero articles fetched! Generating fallback.")
        articles_data = generate_fallback()
        save_news_json(articles_data)
        return

    # 2. 精选
    logger.info("[2/4] Selecting top articles...")
    top = pick_top_articles(all_articles, MAX_ARTICLES)
    articles_data = [a.to_dict() for a in top]
    for i, ad in enumerate(articles_data, 1):
        logger.info(f"  {i}. [{ad['source_name']}] {ad['title'][:70]}")

    # 3. 翻译
    logger.info("[3/4] Translating via DeepSeek...")
    articles_data = translate_articles(articles_data)

    # 4. 下载图片
    logger.info("[4/4] Downloading images...")
    SITE_IMG_DIR.mkdir(parents=True, exist_ok=True)
    for ad in articles_data:
        if ad.get("image_url"):
            ad["local_image"] = download_and_process_image(ad["image_url"]) or ""

    # 5. 保存
    save_news_json(articles_data)
    logger.info("=" * 60)
    logger.info("✓ Daily run complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
