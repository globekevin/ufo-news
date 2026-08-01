"""
UFO 新闻源配置与抓取模块。
支持 RSS 订阅源和网页抓取两种方式，每个源返回标准化 Article 列表。
"""

import hashlib
import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── 请求头（模拟浏览器，避免被反爬） ──────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

class Article:
    """标准化新闻条目"""

    def __init__(
        self,
        title: str,
        url: str,
        summary: str = "",
        image_url: str = "",
        source_name: str = "",
        published: Optional[datetime] = None,
        score: float = 0.0,
        raw_description: str = "",
    ):
        self.title = title.strip()
        self.url = url
        self.summary = summary.strip()
        self.image_url = image_url.strip()
        self.source_name = source_name
        self.published = published or datetime.now()
        self.score = score
        self.raw_description = raw_description.strip()

    @property
    def id(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()[:12]

    @property
    def slug(self) -> str:
        """URL 友好的短标识"""
        clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", self.title[:60]).strip("-")
        return clean or self.id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "image_url": self.image_url,
            "source_name": self.source_name,
            "published": self.published.isoformat(),
            "score": self.score,
            # 翻译后的字段（由 translator 填充）
            "title_cn": "",
            "summary_cn": "",
            "local_image": "",
        }


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _fetch_rss(url: str, source_name: str) -> list[Article]:
    """从 RSS 源抓取文章"""
    articles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries[:20]:  # 取前20条再精选
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not title or not link:
                continue

            # 提取摘要
            summary = ""
            raw_desc = ""
            if hasattr(entry, "summary"):
                raw_desc = BeautifulSoup(entry.summary, "html.parser").get_text(
                    separator=" ", strip=True
                )
            elif hasattr(entry, "description"):
                raw_desc = BeautifulSoup(entry.description, "html.parser").get_text(
                    separator=" ", strip=True
                )
            summary = raw_desc[:300] if raw_desc else ""

            # 提取图片
            image_url = ""
            # Reddit RSS 中图片通常在 media_content 或 content 中
            if hasattr(entry, "media_content"):
                for mc in entry.media_content:
                    if "image" in mc.get("type", ""):
                        image_url = mc.get("url", "")
                        break
            if not image_url and hasattr(entry, "media_thumbnail"):
                for mt in entry.media_thumbnail:
                    image_url = mt.get("url", "")
                    if image_url:
                        break
            # 从 HTML 内容中提取 img
            if not image_url and raw_desc:
                soup = BeautifulSoup(
                    getattr(entry, "summary", raw_desc), "html.parser"
                )
                img = soup.find("img")
                if img and img.get("src"):
                    image_url = img["src"]

            # 解析发布时间
            published = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            # Reddit 风格：从 title 提取 score 估算
            # Reddit RSS 通常有 comments 链接
            score = 1.0
            # 根据新鲜度加分
            hours_ago = (datetime.now() - published).total_seconds() / 3600
            score += max(0, 10 - hours_ago) * 0.5

            articles.append(
                Article(
                    title=title,
                    url=link,
                    summary=summary,
                    image_url=image_url,
                    source_name=source_name,
                    published=published,
                    score=score,
                    raw_description=raw_desc,
                )
            )
    except Exception as e:
        logger.warning(f"RSS fetch failed for {source_name}: {e}")

    return articles


def _fetch_web(url: str, source_name: str, article_selector: str,
               title_sel: str, link_sel: str, img_sel: str = "",
               summary_sel: str = "", base_url: str = "") -> list[Article]:
    """从网页抓取文章列表"""
    articles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        items = soup.select(article_selector)[:15]
        for item in items:
            title_el = item.select_one(title_sel)
            link_el = item.select_one(link_sel)
            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            link = link_el.get("href", "")
            if link and base_url:
                link = urljoin(base_url, link)
            if not link:
                continue

            img_url = ""
            if img_sel:
                img_el = item.select_one(img_sel)
                if img_el:
                    img_url = img_el.get("src") or img_el.get("data-src", "")
                    if img_url and base_url:
                        img_url = urljoin(base_url, img_url)

            summary = ""
            if summary_sel:
                sum_el = item.select_one(summary_sel)
                if sum_el:
                    summary = sum_el.get_text(strip=True)[:300]

            articles.append(
                Article(
                    title=title,
                    url=link,
                    summary=summary,
                    image_url=img_url,
                    source_name=source_name,
                    score=float(len(articles)),  # 按出现顺序给分
                )
            )
    except Exception as e:
        logger.warning(f"Web fetch failed for {source_name}: {e}")

    return articles


# ═══════════════════════════════════════════════════════════════
# 数据源定义
# ═══════════════════════════════════════════════════════════════

# ── RSS 源 ──────────────────────────────────────────────────
RSS_SOURCES = [
    {
        "name": "Reddit r/UFOs",
        "url": "https://www.reddit.com/r/UFOs/.rss",
        "weight": 3.0,  # 最活跃的 UFO 社区
    },
    {
        "name": "Reddit r/aliens",
        "url": "https://www.reddit.com/r/aliens/.rss",
        "weight": 2.5,
    },
    {
        "name": "Reddit r/UFOscience",
        "url": "https://www.reddit.com/r/UFOscience/.rss",
        "weight": 2.0,
    },
    {
        "name": "Reddit r/HighStrangeness",
        "url": "https://www.reddit.com/r/HighStrangeness/.rss",
        "weight": 1.5,
    },
]

# ── 网页抓取源 ──────────────────────────────────────────────
WEB_SOURCES = [
    {
        "name": "Space.com UFO",
        "url": "https://www.space.com/topics/ufos-and-alien-life",
        "article_selector": "article.listing-content, div.listingResult",
        "title_sel": "h3.article-name, h2 a",
        "link_sel": "h3.article-name a, h2 a",
        "img_sel": "img[data-src], img.lazy-image",
        "summary_sel": "p.synopsis, p.description",
        "weight": 2.0,
    },
]


def _fetch_reddit_json(subreddit: str, source_name: str) -> list[Article]:
    """从 Reddit JSON API 抓取（作为 RSS 的降级方案）"""
    articles = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
        resp = requests.get(
            url, headers={**HEADERS, "Accept": "application/json"}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            permalink = post.get("permalink", "")
            if not title or not permalink:
                continue

            link = f"https://www.reddit.com{permalink}"
            # 提取 selftext 作为摘要
            selftext = post.get("selftext", "")[:300]
            score = float(post.get("score", 1))
            ups = post.get("ups", 0)
            num_comments = post.get("num_comments", 0)

            # 提取图片
            image_url = ""
            if post.get("url", "").endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                image_url = post["url"]
            elif post.get("thumbnail") and post["thumbnail"].startswith("http"):
                image_url = post["thumbnail"]
            # 检查 preview 中的图片
            preview = post.get("preview", {})
            images = preview.get("images", [])
            if images and not image_url:
                src = images[0].get("source", {}).get("url", "")
                if src:
                    image_url = src.replace("&amp;", "&")

            # 解析时间
            created = datetime.fromtimestamp(post.get("created_utc", time.time()))

            # Reddit 加权：赞数 + 评论数
            article_score = (ups * 0.1 + num_comments * 0.05 + 1.0)

            articles.append(
                Article(
                    title=title,
                    url=link,
                    summary=selftext,
                    image_url=image_url,
                    source_name=source_name,
                    published=created,
                    score=article_score,
                )
            )
    except Exception as e:
        logger.warning(f"Reddit JSON fetch failed for r/{subreddit}: {e}")

    return articles


def fetch_all_sources() -> list[Article]:
    """从所有源抓取文章，去重后返回"""
    all_articles: list[Article] = []

    # 1. RSS 源
    for src in RSS_SOURCES:
        logger.info(f"Fetching RSS: {src['name']}")
        articles = _fetch_rss(src["url"], src["name"])

        # 如果 RSS 失败，降级到 Reddit JSON API
        if not articles and "Reddit" in src["name"]:
            subreddit = src["url"].split("/r/")[1].split("/")[0]
            logger.info(f"  RSS failed, falling back to Reddit JSON API: r/{subreddit}")
            articles = _fetch_reddit_json(subreddit, src["name"])

        for a in articles:
            a.score *= src["weight"]
        all_articles.extend(articles)
        time.sleep(1.5)

    # 2. 网页源
    for src in WEB_SOURCES:
        logger.info(f"Fetching Web: {src['name']}")
        articles = _fetch_web(
            url=src["url"],
            source_name=src["name"],
            article_selector=src["article_selector"],
            title_sel=src["title_sel"],
            link_sel=src["link_sel"],
            img_sel=src.get("img_sel", ""),
            summary_sel=src.get("summary_sel", ""),
            base_url=src["url"],
        )
        for a in articles:
            a.score *= src["weight"]
        all_articles.extend(articles)
        time.sleep(2)

    # 3. 去重 + 排序
    deduped: list[Article] = []
    seen_urls: set[str] = set()
    for a in all_articles:
        key = a.url.rstrip("/").lower()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        deduped.append(a)

    deduped.sort(key=lambda x: x.score, reverse=True)
    logger.info(f"Total unique articles: {len(deduped)}")
    return deduped


def pick_top_articles(articles: list[Article], count: int = 6) -> list[Article]:
    """
    从文章列表中精选 top N 条。
    策略：优先高分，同时保证来源多样性。
    """
    if len(articles) <= count:
        return articles

    selected = []
    used_sources: set[str] = set()

    # 第一轮：每个源取最高分的 1 条
    for a in articles:
        if len(selected) >= count:
            break
        if a.source_name not in used_sources:
            selected.append(a)
            used_sources.add(a.source_name)

    # 第二轮：补齐剩余位置
    for a in articles:
        if len(selected) >= count:
            break
        if a not in selected:
            selected.append(a)

    return selected[:count]
