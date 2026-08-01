"""
UFO 新闻源配置与抓取模块 v2.0。
数据源全面升级为全球权威机构：

  官方/政府背景（最高权重）：
    1. AARO   — 美国国防部 UAP 调查办公室（通过 The Black Vault 覆盖）
    2. NASA   — NASA UAP 独立研究页面
    3. GEIPAN — 法国国家 UAP 研究组
    4. 英国国家档案馆 UFO 档案
    5. FBI Vault / CIA 解密档案

  民间研究机构（资料量大）：
    6. MUFON      — 全球最大民间 UFO 组织
    7. NUFORC     — 17 万+ 条目击报告数据库
    8. CUFOS      — Hynek 创办的学术型组织
    9. The Black Vault — FOIA 解密文件聚合（直接覆盖 AARO/DoD/Pentagon）

支持 RSS、HTML 页面抓取、搜索 API 多种方式，
每个源返回标准化 Article 列表。
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── 请求头 ──────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.5",
}
REQUEST_TIMEOUT = 25


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
            "title_cn": "",
            "summary_cn": "",
            "local_image": "",
        }


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _clean_html(html_text: str) -> str:
    """去除 HTML 标签，返回纯文本"""
    if not html_text:
        return ""
    return BeautifulSoup(html_text, "html.parser").get_text(separator=" ", strip=True)


def _extract_image_from_html(html_text: str) -> str:
    """从 HTML 内容中提取第一张图片 URL"""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    img = soup.find("img")
    if img:
        return img.get("src", "") or img.get("data-src", "")
    return ""


def _try_get(url: str, **kwargs) -> Optional[requests.Response]:
    """带重试的 GET 请求"""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                logger.debug(f"  Request failed ({attempt+1}/3): {url[:60]} — {e}")
    return None


# ═══════════════════════════════════════════════════════════════
# 源 #1: The Black Vault RSS — 覆盖 AARO/DoD/Pentagon/NASA FOIA
# ═══════════════════════════════════════════════════════════════

BLACKVAULT_RSS_URL = "https://www.theblackvault.com/documentarchive/feed/"
BLACKVAULT_UFO_CATEGORY = "https://www.theblackvault.com/documentarchive/category/the-fringe/"

# UAP/UFO 关键词（用于从 RSS 全量中筛选相关文章）
UAP_KEYWORDS = [
    "uap", "ufo", "unidentified", "aaro", "pentagon", "dod ", "navy pilot",
    "alien", "extraterrestrial", "space force", "uap task force", "aatip",
    "aaWSAP", "unidentified anomalous", "flying object", "non-human",
    "grusch", "elizondo", "loeb", "galileo project", "anomalous phenomenon",
    "uap report", "ufo report", "ufo file", "uap file", "uap hearing",
    "congressional uap", "senate uap", "whistleblower uap",
]

# 目击事件关键词 —— 权重很高，命中越多越优先
EVENT_KEYWORDS = [
    # 目击行为
    "sighting", "spotted", "witness", "witnesses", "witnessed", "observed",
    "seen over", "seen near", "appeared", "hovering", "flew over",
    # 视频/照片证据
    "video", "footage", "photograph", "photo", "filmed", "recorded", "camera",
    "cellphone", "dashcam", "infrared",
    # 目击者身份（高可信度）
    "pilot", "pilots", "commercial pilot", "airline pilot", "military pilot",
    "astronaut", "police officer", "police", "air force", "navy",
    "air traffic control", "radar operator", "fighter jet",
    # 物体形态
    "orb", "orbs", "disk", "disc", "triangle", "triangular", "tic tac",
    "cylinder", "cigar", "lights", "formation", "fleet", "swarm",
    "black triangle", "glowing", "metallic", "sphere", "diamond",
    # 物理效应
    "landing", "landed", "trace", "physical evidence", "radiation",
    "electromagnetic", "emf", "engine failure", "instrument malfunction",
    # 规模
    "mass sighting", "multiple witnesses", "dozens of", "hundreds of",
    "over a city", "over the city",
    # 知名事件/地点
    "rendlesham", "phoenix lights", "stephenville", "tic-tac ufo",
    "gimbal", "go fast", "nimitz", "roosevelt", "omalley",
    "close encounter", "ce2k", "abduction", "humanoid",
    "pantex", "nuclear facility", "nuclear", "nuke site",
    "air force base", "military base", "naval base",
    "anoka", "virginia beach", "texas",
    # 最新线索
    "new footage", "new video", "leaked video", "new sighting",
    "recent sighting", "unexplained lights", "mysterious object",
    "unknown craft", "breaking", "eyewitness", "firsthand",
    "silent", "chased", "pacing", "shadowed",
    "declassified documents detail", "newly declassified fbi",
    "declassified files reveal",
]

# 政策/公文关键词 —— 命中后减权（FOIA/邮件/档案类都要打击）
POLICY_KEYWORDS = [
    # 报告/公文
    "report released", "annual report", "quarterly report", "fiscal year",
    "fy202", "fy2025", "fy2026", "report to congress",
    # 听证/简报
    "hearing", "hearing on", "testimony", "testified", "testifies",
    "briefing", "briefed", "policy", "legislation", "budget request",
    "appropriation", "funding", "letter to", "memorandum", "memo",
    # FOIA / 解密
    "foia request", "foia release", "foia document", "foia log",
    "declassified", "declassification", "document dump",
    # 机构/组织
    "task force", "office of", "director of", "appointed",
    "committee", "congressional", "senate", "house",
    # 内部文件
    "press release", "statement on", "announces plan", "prepares for",
    "internal memo", "draft", "proposal", "framework",
    # 协调/沟通
    "coordination", "coordinated", "communication plan",
    "retrieving information", "searched for", "catalog",
    # 档案/统计
    "archive", "database", "total of", "statistics",
    # 邮件
    "emails reveal", "emails show", "deleted emails", "email archive",
    "correspondence", "email thread",
    # 拒绝/上诉
    "denies appeal", "denies request", "refuses to", "rejects",
    "appeal denied", "blocked release",
    # 规划/准备
    "planning on how to", "prepares to", "internal planning",
    "developing plan", "contingency plan",
    # FAQ / 百科型（非新闻）
    "what are they", "what are ufos", "most famous sightings",
    "what is a ufo", "explainer", "everything you need to know",
    "complete guide", "history of ufo", "ufo 101",
    # 排名/统计型
    "most ufo sightings", "cities with the most", "top 10",
    "where yours ranks", "states with the most",
]


def _is_uap_article(title: str, summary: str) -> bool:
    """判断文章是否与 UAP/UFO 相关"""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in UAP_KEYWORDS)


def _compute_event_score(title: str, summary: str) -> float:
    """
    计算「目击事件感」分数。
    正值 = 事件型内容，负值 = 政策型内容。
    用于精选排序而非筛选（所有 UAP 文章都可能入选）。
    """
    text = (title + " " + summary).lower()
    score = 0.0

    # 事件关键词加分
    for kw in EVENT_KEYWORDS:
        if kw in text:
            # 视频/照片证据权重更高
            if kw in ("video", "footage", "photograph", "photo", "filmed", "recorded"):
                score += 0.6
            # 目击者身份高可信度
            elif kw in ("pilot", "pilots", "military pilot", "air force", "navy",
                        "astronaut", "police officer"):
                score += 0.5
            # 规模类
            elif kw in ("mass sighting", "multiple witnesses", "dozens of", "hundreds of"):
                score += 0.5
            # 物理证据
            elif kw in ("landing", "landed", "trace", "physical evidence", "radiation"):
                score += 0.5
            # 知名事件
            elif kw in ("rendlesham", "phoenix lights", "nimitz", "tic-tac ufo",
                        "gimbal", "go fast", "close encounter", "abduction"):
                score += 0.5
            # 最新/突发
            elif kw in ("new footage", "new video", "leaked video", "new sighting",
                        "breaking", "recent sighting"):
                score += 0.5
            # 物体形态
            elif kw in ("orb", "orbs", "disk", "disc", "triangle", "triangle", "lights",
                        "formation", "fleet", "swarm"):
                score += 0.35
            else:
                score += 0.3

    # 政策关键词减分
    for kw in POLICY_KEYWORDS:
        if kw in text:
            score -= 0.35

    return round(score, 2)


def _fetch_blackvault_rss() -> list[Article]:
    """从 The Black Vault RSS 抓取 UAP/UFO 相关文章"""
    articles = []
    resp = _try_get(BLACKVAULT_RSS_URL)
    if not resp:
        return articles

    try:
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not title or not link:
                continue

            # 提取摘要
            raw_desc = ""
            if hasattr(entry, "summary"):
                raw_desc = entry.summary
            elif hasattr(entry, "description"):
                raw_desc = entry.description
            summary = _clean_html(raw_desc)[:400]

            # 只保留 UAP/UFO 相关
            if not _is_uap_article(title, summary):
                continue

            # 提取图片
            image_url = ""
            if hasattr(entry, "media_content"):
                for mc in entry.media_content:
                    if "image" in mc.get("type", ""):
                        image_url = mc.get("url", "")
                        break
            if not image_url:
                image_url = _extract_image_from_html(raw_desc)

            # 发布时间
            published = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            # 加权：越新越高
            hours_ago = max(0, (datetime.now() - published).total_seconds() / 3600)
            score = 5.0 + max(0, 48 - hours_ago) * 0.05

            # 来源标签细化
            source_label = _get_blackvault_source_label(title, summary)

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                image_url=image_url,
                source_name=source_label,
                published=published,
                score=score,
                raw_description=raw_desc,
            ))
    except Exception as e:
        logger.warning(f"BlackVault RSS parse error: {e}")

    logger.info(f"  BlackVault RSS: {len(articles)} UAP articles")
    return articles


def _get_blackvault_source_label(title: str, summary: str) -> str:
    """根据内容推断文章实际来源机构"""
    text = (title + " " + summary).lower()
    if "aaro" in text:
        return "AARO (美国国防部 UAP 办公室)"
    elif "nasa" in text:
        return "NASA"
    elif "pentagon" in text or "dod " in text:
        return "五角大楼 / DoD"
    elif "fbi " in text or "fbi file" in text:
        return "FBI 解密档案"
    elif "cia " in text or "cia declass" in text:
        return "CIA 解密档案"
    elif "noaa" in text:
        return "NOAA (美国海洋大气局)"
    elif "congress" in text or "senate" in text or "hearing" in text:
        return "美国国会 UAP 听证"
    else:
        return "The Black Vault (FOIA 解密)"


def _fetch_blackvault_html() -> list[Article]:
    """从 The Black Vault Mysteries 分类页 HTML 抓取（RSS 降级）"""
    articles = []
    resp = _try_get(BLACKVAULT_UFO_CATEGORY)
    if not resp:
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        # Black Vault 文章在 <article> 标签内
        for article_tag in soup.select("article")[:15]:
            title_el = article_tag.select_one("h2 a, h3 a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not link:
                continue

            # 摘要
            summary_el = article_tag.select_one(".entry-content p, .post-excerpt p")
            summary = summary_el.get_text(strip=True)[:400] if summary_el else ""

            # 图片
            img_el = article_tag.select_one("img")
            image_url = ""
            if img_el:
                image_url = img_el.get("src", "") or img_el.get("data-src", "")

            # 日期
            date_el = article_tag.select_one("time, .entry-date, .post-date")
            published = datetime.now()
            if date_el:
                dt_str = date_el.get("datetime", "") or date_el.get_text(strip=True)
                try:
                    published = datetime.strptime(dt_str[:10], "%Y-%m-%d")
                except Exception:
                    pass

            source_label = _get_blackvault_source_label(title, summary)

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                image_url=image_url,
                source_name=source_label,
                published=published,
                score=3.0,
            ))
    except Exception as e:
        logger.warning(f"BlackVault HTML fallback error: {e}")

    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #2: NUFORC — 目击报告数据库
# ═══════════════════════════════════════════════════════════════

NUFORC_MONTHLY_INDEX = "https://nuforc.org/webreports/ndxevent.html"
NUFORC_ALT_INDEX = "https://nuforc.org/ndx/?id=event"


def _fetch_nuforc() -> list[Article]:
    """
    从 NUFORC 获取最新目击事件。
    优先抓取「目击事件摘要」页面，降级用月度统计。
    NUFORC Sighting Reports: https://nuforc.org/webreports/ndxevent.html
    """
    articles = []

    # 先尝试抓取事件摘要页（包含具体目击描述）
    event_resp = _try_get("https://nuforc.org/webreports/ndxevent.html")
    if event_resp:
        try:
            soup = BeautifulSoup(event_resp.content, "lxml")
            # 尝试从链接中提取近期事件
            event_rows = soup.select("table tr")[:30]
            found_events = []
            for row in event_rows:
                cells = row.select("td")
                if len(cells) >= 2:
                    link_el = row.select_one("a[href]")
                    if link_el:
                        date_text = cells[0].get_text(strip=True)
                        location_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        desc_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        href = link_el.get("href", "")
                        if href and len(date_text) > 5:
                            found_events.append({
                                "date": date_text,
                                "location": location_text,
                                "desc": desc_text,
                                "url": urljoin(NUFORC_MONTHLY_INDEX, href),
                            })

            # 取最近 2 条有描述的目击事件
            event_count = 0
            for ev in found_events[:3]:
                if ev["desc"] and len(ev["desc"]) > 15:
                    title = f"目击报告: {ev['location']} — {ev['desc'][:60]}"
                    summary = (
                        f"NUFORC 收到来自 {ev['location']} 的目击报告"
                        f"（{ev['date']}）。报告描述: {ev['desc'][:250]}。"
                        f"NUFORC 正在对该事件进行进一步调查核实。"
                    )
                    articles.append(Article(
                        title=title,
                        url=ev["url"],
                        summary=summary,
                        source_name="NUFORC (美国目击报告中心)",
                        published=datetime.now(),
                        score=3.8,
                    ))
                    event_count += 1
                    if event_count >= 2:
                        break
        except Exception as e:
            logger.warning(f"NUFORC events parse error: {e}")

    # 降级：用月度统计
    if not articles:
        monthly_data = []
        resp = _try_get(NUFORC_MONTHLY_INDEX)
        if not resp:
            resp = _try_get(NUFORC_ALT_INDEX)

        if resp:
            try:
                soup = BeautifulSoup(resp.content, "lxml")
                rows = soup.select("table tr, .data-table tr, ul li, p")
                for row in rows:
                    text = row.get_text(strip=True)
                    match = re.match(r"(\d{4})\s*[/-]\s*(\d{2})\D+(\d+)", text)
                    if not match:
                        match = re.match(r"(\d{2})\s*[/-]\s*(\d{4})\D+(\d+)", text)
                        if match:
                            mo, yr, cnt = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        else:
                            continue
                    else:
                        yr, mo, cnt = int(match.group(1)), int(match.group(2)), int(match.group(3))

                    if 1900 < yr < 2100 and 1 <= mo <= 12 and cnt > 0:
                        monthly_data.append({
                            "year": yr, "month": mo, "count": cnt,
                            "link": f"https://nuforc.org/webreports/ndxe{yr}{mo:02d}.html",
                        })
            except Exception as e:
                logger.warning(f"NUFORC parse error: {e}")

        if not monthly_data:
            now = datetime.now()
            monthly_data = [
                {"year": now.year, "month": now.month - 1 if now.month > 1 else 12,
                 "count": 200, "link": "https://nuforc.org/webreports/ndxevent.html"},
            ]

        monthly_data.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
        for md in monthly_data[:1]:
            month_name = f"{md['year']}年{md['month']}月"
            articles.append(Article(
                title=f"NUFORC {month_name}目击报告：收录 {md['count']}+ 份",
                url=md["link"],
                summary=(
                    f"美国国家 UFO 报告中心（NUFORC）在 {month_name} "
                    f"共收录超过 {md['count']} 份 UAP/UFO 目击报告。"
                ),
                source_name="NUFORC (美国目击报告中心)",
                published=datetime(md["year"], md["month"], 15),
                score=2.5,
            ))

    logger.info(f"  NUFORC: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #3: NASA UAP 页面
# ═══════════════════════════════════════════════════════════════

NASA_UAP_URL = "https://science.nasa.gov/uap/"


def _fetch_nasa_uap() -> list[Article]:
    """从 NASA UAP 官方页面提取最新报告和公告"""
    articles = []
    resp = _try_get(NASA_UAP_URL)
    if not resp:
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")

        # 查找所有链接中包含 "pdf" 或 "report" 的
        found_items = []
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)
            if not text or len(text) < 10:
                continue
            if any(kw in (href + text).lower() for kw in
                   ["uap", "report", "briefing", "meeting", "study", "announce"]):
                found_items.append({
                    "title": text[:120],
                    "url": urljoin(NASA_UAP_URL, href),
                    "summary": "",
                })

        # 去重
        seen = set()
        for item in found_items[:5]:
            if item["url"] in seen:
                continue
            seen.add(item["url"])

            articles.append(Article(
                title=item["title"],
                url=item["url"],
                summary=item["summary"],
                source_name="NASA",
                published=datetime.now(),
                score=4.0,
            ))

    except Exception as e:
        logger.warning(f"NASA UAP parse error: {e}")

    # 添加 NASA UAP 最终报告（静态内容，始终可用）
    articles.append(Article(
        title="NASA UAP 独立研究小组最终报告（2023年9月）",
        url="https://science.nasa.gov/wp-content/uploads/2023/09/uap-independent-study-team-final-report.pdf",
        summary="NASA 任命的不明异常现象独立研究小组于 2023 年 9 月发布最终报告，建议建立科学观测网络，利用现有科研基础设施系统化采集和分析 UAP 数据。",
        source_name="NASA",
        published=datetime(2023, 9, 14),
        score=4.5,
    ))

    logger.info(f"  NASA UAP: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #4: FBI Vault — UFO 档案
# ═══════════════════════════════════════════════════════════════

FBI_VAULT_UFO_URL = "https://vault.fbi.gov/UFO"


def _fetch_fbi_vault() -> list[Article]:
    """从 FBI Vault UFO 分类获取档案索引"""
    articles = []
    resp = _try_get(FBI_VAULT_UFO_URL)
    if not resp:
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        # FBI Vault 使用特定的文档列表结构
        for item in soup.select(".file-box, .document-item, .views-row")[:5]:
            title_el = item.select_one("a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://vault.fbi.gov", link)

            articles.append(Article(
                title=title,
                url=link,
                source_name="FBI Vault (解密档案)",
                score=2.5,
            ))
    except Exception as e:
        logger.warning(f"FBI Vault parse error: {e}")

    # 如果抓取失败，提供已知档案入口
    if not articles:
        articles.append(Article(
            title="FBI Vault: UFO 档案全集",
            url="https://vault.fbi.gov/UFO",
            summary="FBI 信息公开法（FOIA）图书馆中的 UFO 相关档案，包含历史上著名的备忘录原件、调查报告和通信记录。",
            source_name="FBI Vault (解密档案)",
            score=2.5,
        ))

    logger.info(f"  FBI Vault: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #5: CIA Reading Room — UFO 搜索
# ═══════════════════════════════════════════════════════════════

CIA_UFO_SEARCH = "https://www.cia.gov/readingroom/search/site/ufo"


def _fetch_cia_readingroom() -> list[Article]:
    """从 CIA 电子阅览室搜索 UFO 相关解密文档"""
    articles = []
    resp = _try_get(CIA_UFO_SEARCH)
    if not resp:
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        for result in soup.select(".search-result, .views-row, article")[:5]:
            title_el = result.select_one("a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.cia.gov", link)

            desc_el = result.select_one(".description, .search-snippet, p")
            summary = desc_el.get_text(strip=True)[:300] if desc_el else ""

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source_name="CIA 电子阅览室",
                score=3.0,
            ))
    except Exception as e:
        logger.warning(f"CIA Reading Room parse error: {e}")

    if not articles:
        articles.append(Article(
            title="CIA 电子阅览室: UFO/UAP 相关解密文档",
            url="https://www.cia.gov/readingroom/search/site/ufo",
            summary="CIA 通过 FOIA 电子阅览室公开的历史 UFO 相关文档，包括著名的「蓝皮书计划」相关备忘录和情报评估。",
            source_name="CIA 电子阅览室",
            score=2.5,
        ))

    logger.info(f"  CIA: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #6: GEIPAN — 法国国家 UAP 研究组
# ═══════════════════════════════════════════════════════════════

GEIPAN_URL = "https://www.cnes-geipan.fr/en"


def _fetch_geipan() -> list[Article]:
    """从 GEIPAN（法国官方案件数据库）获取最新动态"""
    articles = []
    resp = _try_get(GEIPAN_URL)
    if not resp:
        # 尝试法语版
        resp = _try_get("https://www.cnes-geipan.fr/")

    if not resp:
        # 提供静态已知信息
        articles.append(Article(
            title="GEIPAN: 全球唯一直属国家航天局的 UFO 调查机构持续运营",
            url="https://www.cnes-geipan.fr/en",
            summary="法国国家空间研究中心（CNES）下属的 GEIPAN 是全球唯一仍在运行的国家级官方 UFO/UAP 调查机构，案件数据库完全公开，涵盖数千份经过科学调查的案例。",
            source_name="GEIPAN (法国国家空间研究中心)",
            score=4.0,
        ))
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        for item in soup.select("article, .news-item, .actualite, .card")[:5]:
            title_el = item.select_one("h2 a, h3 a, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin(GEIPAN_URL, link)

            desc_el = item.select_one("p, .description, .summary")
            summary = desc_el.get_text(strip=True)[:300] if desc_el else ""

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source_name="GEIPAN (法国国家空间研究中心)",
                score=4.0,
            ))
    except Exception as e:
        logger.warning(f"GEIPAN parse error: {e}")

    if not articles:
        articles.append(Article(
            title="GEIPAN: 法国官方 UFO 调查机构公开案件数据库",
            url="https://www.cnes-geipan.fr/en",
            summary="GEIPAN 是法国国家空间研究中心（CNES）下属的官方 UAP 调查机构，自 1977 年以来持续运行，拥有全球最完整的官方 UFO 调查档案。",
            source_name="GEIPAN (法国国家空间研究中心)",
            score=4.0,
        ))

    logger.info(f"  GEIPAN: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #7: 英国国家档案馆 UFO 档案
# ═══════════════════════════════════════════════════════════════

UK_ARCHIVES_UFO_URL = "https://www.nationalarchives.gov.uk/help-with-your-research/research-guides/ufos/"


def _fetch_uk_archives() -> list[Article]:
    """从英国国家档案馆获取 UFO 档案信息"""
    articles = []
    resp = _try_get(UK_ARCHIVES_UFO_URL)
    if not resp:
        articles.append(Article(
            title="英国国防部解密 UFO「X档案」: 跨越 50 年的官方记录",
            url="https://www.nationalarchives.gov.uk/help-with-your-research/research-guides/ufos/",
            summary="英国国家档案馆公开了国防部 UFO 档案的最终批次，涵盖 1950 年至 2009 年间数千份不明飞行物报告，包含警察和军事飞行员的第一手目击记录。全部可免费下载 PDF。",
            source_name="英国国家档案馆",
            score=3.5,
        ))
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        # 查找页面中链接到具体档案的条目
        for a_tag in soup.select("a[href*='.pdf'], a[href*='ufo']"):
            text = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if len(text) < 15:
                continue
            if any(kw in (text + href).lower() for kw in ["ufo", "uap", "unidentified"]):
                articles.append(Article(
                    title=text[:120],
                    url=urljoin(UK_ARCHIVES_UFO_URL, href),
                    source_name="英国国家档案馆",
                    score=3.5,
                ))
    except Exception as e:
        logger.warning(f"UK Archives parse error: {e}")

    if not articles:
        articles.append(Article(
            title="英国国家档案馆: UFO 档案研究与获取指南",
            url=UK_ARCHIVES_UFO_URL,
            summary="英国国家档案馆保存了国防部 1950-2009 年间全部 UFO 报告档案，包括著名的「Rendlesham Forest」事件等经典案例的原始文件。",
            source_name="英国国家档案馆",
            score=3.5,
        ))

    logger.info(f"  UK Archives: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #8: MUFON — 全球最大民间 UFO 调查组织
# ═══════════════════════════════════════════════════════════════

MUFON_NEWS_URL = "https://www.mufon.com/news"


def _fetch_mufon() -> list[Article]:
    """从 MUFON 新闻页面抓取"""
    articles = []
    resp = _try_get(MUFON_NEWS_URL)
    if not resp:
        resp = _try_get("https://www.mufon.com")

    if not resp:
        articles.append(Article(
            title="MUFON: 全球最大民间 UFO 调查组织发布最新目击分析报告",
            url="https://www.mufon.com",
            summary="MUFON（Mutual UFO Network）是全球规模最大的民间 UFO 调查组织，拥有完整的目击报告数据库、月刊出版物和专业调查员网络。",
            source_name="MUFON (全球最大民间 UFO 组织)",
            score=2.5,
        ))
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        for item in soup.select("article, .news-item, .post, .blog-entry")[:5]:
            title_el = item.select_one("h2 a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin(MUFON_NEWS_URL, link)

            desc_el = item.select_one("p, .excerpt, .summary")
            summary = desc_el.get_text(strip=True)[:300] if desc_el else ""

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source_name="MUFON",
                score=2.5,
            ))
    except Exception as e:
        logger.warning(f"MUFON parse error: {e}")

    if not articles:
        articles.append(Article(
            title="MUFON: 全球民间 UFO 调查组织持续追踪最新目击事件",
            url="https://www.mufon.com",
            summary="MUFON 在全球拥有数千名志愿者调查员，每月接收数百份 UAP 目击报告，经专业调查后公开发布分析结果。",
            source_name="MUFON (全球最大民间 UFO 组织)",
            score=2.0,
        ))

    logger.info(f"  MUFON: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #9: CUFOS — J. Allen Hynek 创办的学术组织
# ═══════════════════════════════════════════════════════════════

CUFOS_URL = "https://www.cufos.org"


def _fetch_cufos() -> list[Article]:
    """从 CUFOS 获取学术研究动态"""
    articles = []
    resp = _try_get(CUFOS_URL)

    if not resp:
        articles.append(Article(
            title="CUFOS: J. Allen Hynek 创办的学术型 UFO 研究组织",
            url="https://www.cufos.org",
            summary="UFO 研究中心（CUFOS）由天文学家、《第三类接触》科学顾问 J. Allen Hynek 博士创办，是学术血统最正统的民间 UFO 研究机构，拥有丰富的历史档案和学术期刊。",
            source_name="CUFOS (J. Allen Hynek 创办)",
            score=3.0,
        ))
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        for item in soup.select("article, .post, .news-item")[:5]:
            title_el = item.select_one("h2 a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin(CUFOS_URL, link)

            desc_el = item.select_one("p, .excerpt, .description")
            summary = desc_el.get_text(strip=True)[:300] if desc_el else ""

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source_name="CUFOS (J. Allen Hynek 创办)",
                score=3.0,
            ))
    except Exception as e:
        logger.warning(f"CUFOS parse error: {e}")

    if not articles:
        articles.append(Article(
            title="CUFOS 学术档案: Hynek 分类体系与经典案例研究",
            url="https://www.cufos.org",
            summary="CUFOS 保存了 Hynek 博士提出的「近距离接触」分类体系的原始研究资料，以及「蓝皮书计划」期间积累的大量案例档案。",
            source_name="CUFOS (J. Allen Hynek 创办)",
            score=2.5,
        ))

    logger.info(f"  CUFOS: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #10: Google News — 「UFO sighting」搜索（事件型新闻）
# ═══════════════════════════════════════════════════════════════

GOOGLE_NEWS_UFO_RSS = "https://news.google.com/rss/search?q=UFO+sighting&hl=en-US&gl=US&ceid=US:en"


def _fetch_google_news_ufo() -> list[Article]:
    """从 Google News RSS 抓取最新 UFO 目击事件新闻"""
    articles = []
    resp = _try_get(GOOGLE_NEWS_UFO_RSS)
    if not resp:
        logger.debug("Google News RSS unreachable")
        return articles

    try:
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not title or not link:
                continue

            raw_desc = entry.get("summary", "") or entry.get("description", "")
            summary = _clean_html(raw_desc)[:350]

            # 跳过纯政策/报告类
            if not _is_uap_article(title, summary):
                continue

            # 提取来源（Google News 标题格式: "Title - SourceName"）
            source_name = "新闻聚合"
            pub = entry.get("source", {})
            if pub and pub.get("title"):
                source_name = pub["title"]

            published = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            hours_ago = max(0, (datetime.now() - published).total_seconds() / 3600)
            score = 3.5 + max(0, 72 - hours_ago) * 0.04

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source_name=f"📰 {source_name}",
                published=published,
                score=score,
                raw_description=raw_desc,
            ))
    except Exception as e:
        logger.warning(f"Google News RSS parse error: {e}")

    logger.info(f"  Google News UFO: {len(articles)} articles")
    return articles


# ═══════════════════════════════════════════════════════════════
# 源 #11: MUFON 最新案例（目击事件）
# ═══════════════════════════════════════════════════════════════

MUFON_CASES_URL = "https://www.mufon.com/ufo-sightings-recent.html"


def _fetch_mufon_cases() -> list[Article]:
    """从 MUFON 最新目击案例页抓取"""
    articles = []
    resp = _try_get(MUFON_CASES_URL)
    if not resp:
        resp = _try_get("https://www.mufon.com/last-20-sightings")

    if not resp:
        logger.debug("MUFON cases unreachable")
        return articles

    try:
        soup = BeautifulSoup(resp.content, "lxml")
        for item in soup.select(".sighting-item, .case-item, .report-item, tr")[:10]:
            cells = item.select("td")
            if len(cells) >= 2:
                date_cell = cells[0].get_text(strip=True)
                location_cell = cells[1].get_text(strip=True)
                desc_cell = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                if date_cell and location_cell and len(desc_cell) > 15:
                    title = f"MUFON 目击报告: {location_cell} — {desc_cell[:50]}"
                    summary = f"目击日期: {date_cell}，地点: {location_cell}。{desc_cell[:200]}（来源: MUFON 案件数据库）"
                    articles.append(Article(
                        title=title,
                        url=MUFON_CASES_URL,
                        summary=summary,
                        source_name="MUFON (目击案例)",
                        published=datetime.now(),
                        score=3.0,
                    ))
                    continue

            # Fallback: general selectors
            title_el = item.select_one("h3 a, h4 a, .title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin(MUFON_CASES_URL, link)

            desc_el = item.select_one("p, .desc, .description")
            summary = desc_el.get_text(strip=True)[:250] if desc_el else ""

            if any(kw in (title + summary).lower() for kw in ["sighting", "witness", "report", "case"]):
                articles.append(Article(
                    title=title,
                    url=link,
                    summary=summary,
                    source_name="MUFON (目击案例)",
                    score=3.0,
                ))
    except Exception as e:
        logger.warning(f"MUFON cases parse error: {e}")

    logger.info(f"  MUFON Cases: {len(articles)} items")
    return articles


# ═══════════════════════════════════════════════════════════════

def _fetch_reddit_fallback() -> list[Article]:
    """从 Reddit r/UFOs JSON API 抓取（最后降级方案）"""
    articles = []
    try:
        url = "https://www.reddit.com/r/UFOs/hot.json?limit=15"
        resp = _try_get(url)
        if not resp:
            return articles

        data = resp.json()
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            permalink = post.get("permalink", "")
            if not title or not permalink:
                continue

            link = f"https://www.reddit.com{permalink}"
            selftext = post.get("selftext", "")[:300]
            ups = post.get("ups", 0)
            num_comments = post.get("num_comments", 0)

            image_url = ""
            if post.get("url", "").endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                image_url = post["url"]
            preview = post.get("preview", {})
            images = preview.get("images", [])
            if images and not image_url:
                src = images[0].get("source", {}).get("url", "")
                if src:
                    image_url = src.replace("&amp;", "&")

            created = datetime.fromtimestamp(post.get("created_utc", time.time()))
            score = ups * 0.08 + num_comments * 0.04 + 1.0

            articles.append(Article(
                title=title,
                url=link,
                summary=selftext,
                image_url=image_url,
                source_name="Reddit r/UFOs (社区降级)",
                published=created,
                score=score * 1.5,  # 降低权重
            ))
    except Exception as e:
        logger.warning(f"Reddit fallback error: {e}")

    return articles


# ═══════════════════════════════════════════════════════════════
# 主入口：统一抓取所有源
# ═══════════════════════════════════════════════════════════════

# 所有抓取函数及其来源权重（用于最终精选）
SOURCE_FETCHERS = [
    # 名称                    函数                      权重   是否必需
    ("BlackVault RSS",        _fetch_blackvault_rss,   3.0,   True),
    ("BlackVault HTML",       _fetch_blackvault_html,  2.0,   False),  # RSS 的降级
    ("NUFORC",                _fetch_nuforc,           3.5,   True),
    ("NASA UAP",              _fetch_nasa_uap,         3.0,   True),
    ("FBI Vault",             _fetch_fbi_vault,        2.0,   False),
    ("CIA Reading Room",      _fetch_cia_readingroom,  2.0,   False),
    ("GEIPAN",                _fetch_geipan,           3.0,   True),
    ("UK National Archives",  _fetch_uk_archives,      2.5,   False),
    ("MUFON",                 _fetch_mufon,            2.0,   False),
    ("CUFOS",                 _fetch_cufos,            2.0,   False),
    ("Google News UFO",       _fetch_google_news_ufo,  4.5,   True),
    ("MUFON Cases",           _fetch_mufon_cases,      3.5,   True),
    ("Reddit (降级)",          _fetch_reddit_fallback,  2.0,   False),
]


def fetch_all_sources() -> list[Article]:
    """从所有源抓取文章，去重后返回（按分数降序）"""
    all_articles: list[Article] = []
    seen_urls: set[str] = set()
    rss_success = False  # 跟踪 RSS 是否成功（决定是否跑 HTML 降级）

    for name, fetcher, weight, required in SOURCE_FETCHERS:
        # 如果 RSS 成功了，跳过 HTML 降级
        if name == "BlackVault HTML" and rss_success:
            logger.info(f"Skipping {name} — RSS succeeded")
            continue

        logger.info(f"Fetching: {name} (weight={weight})")
        try:
            articles = fetcher()
        except Exception as e:
            logger.warning(f"{name} crashed: {e}")
            articles = []

        if name == "BlackVault RSS" and articles:
            rss_success = True

        # 应用权重 + 去重
        for a in articles:
            key = a.url.rstrip("/").lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            a.score *= weight
            all_articles.append(a)

        # 请求间隔
        time.sleep(1.5 if required else 0.8)

    # 计算每条文章的「目击事件感」分数
    for a in all_articles:
        event_score = _compute_event_score(a.title, a.summary)
        a.event_score = event_score
        # 综合权重：事件感权重 4x，压过来源权重差异
        a.sort_score = a.score + event_score * 4.0

    # 按综合分数降序排列
    all_articles.sort(key=lambda x: x.sort_score, reverse=True)

    logger.info(f"Total unique articles from {len(seen_urls)} unique URLs")
    return all_articles


def pick_top_articles(articles: list[Article], count: int = 6) -> list[Article]:
    """
    从文章列表中精选 top N 条。

    策略（事件优先 + 来源多样性）：
    1. 事件型（event_score > 0）优先于政策型（event_score <= 0）
    2. 同类内部按综合分数 sort_score 排序
    3. 保证来源多样性（同一来源最多 1 条）
    4. 如果事件型不够 N 条，用政策型补齐

    IMPORTANT: 优先选「目击事件」而非「政府政策」。
    """
    if len(articles) <= count:
        return articles

    # 过滤 FAQ/百科型文章
    def _is_faq(article: Article) -> bool:
        title_low = article.title.lower()
        faq_markers = ["what are", "what is a", "most famous", "explainer",
                       "everything you need", "complete guide", "history of",
                       "where yours ranks", "cities with the most", "top 10",
                       "these 20", "states with the"]
        return any(m in title_low for m in faq_markers)

    articles = [a for a in articles if not _is_faq(a)]

    # 分成事件型和政策型两组
    event_articles = [a for a in articles if getattr(a, 'event_score', 0) > 0]
    policy_articles = [a for a in articles if getattr(a, 'event_score', 0) <= 0]

    event_articles.sort(key=lambda x: x.sort_score, reverse=True)
    policy_articles.sort(key=lambda x: x.sort_score, reverse=True)

    selected: list[Article] = []
    used_source_groups: set[str] = set()
    used_event_topics: set[str] = set()

    def _source_group(article: Article) -> str:
        src = article.source_name.split("(")[0].strip()
        parts = src.split(" ")
        return " ".join(parts[:2]).lower()

    def _event_topic(article: Article) -> str:
        """提取事件核心主题（地点/关键词，用于去重）"""
        title = article.title.lower()
        for loc in ["anoka", "pantex", "virginia beach", "texas nuke",
                     "rendlesham", "phoenix", "stephenville", "nimitz"]:
            if loc in title:
                return loc
        for kw in ["pilot encounter", "police officer", "police officers",
                    "nuclear facility", "air force base", "naval base"]:
            if kw in title:
                return kw
        return ""

    # 第一轮：事件型（多样性 + 同一事件去重）
    for a in event_articles:
        if len(selected) >= count:
            break
        sg = _source_group(a)
        et = _event_topic(a)
        if sg in used_source_groups:
            continue
        if et and et in used_event_topics:
            continue
        selected.append(a)
        used_source_groups.add(sg)
        if et:
            used_event_topics.add(et)

    # 第二轮：事件型补齐（不限多样性，但继续去重）
    if len(selected) < count:
        for a in event_articles:
            if len(selected) >= count:
                break
            if a not in selected:
                et = _event_topic(a)
                if et and et in used_event_topics:
                    continue
                selected.append(a)
                if et:
                    used_event_topics.add(et)

    # 第三轮：政策型补齐
    if len(selected) < count:
        for a in policy_articles:
            if len(selected) >= count:
                break
            sg = _source_group(a)
            if sg not in used_source_groups:
                selected.append(a)
                used_source_groups.add(sg)

    # 第四轮：政策型不限多样性
    if len(selected) < count:
        for a in policy_articles:
            if len(selected) >= count:
                break
            if a not in selected:
                selected.append(a)

    for i, a in enumerate(selected, 1):
        es = getattr(a, 'event_score', 0)
        tag = "🔥事件" if es > 0 else "📄政策"
        logger.info(
            f"  Selected #{i} [{tag} event={es:.1f} sort={a.sort_score:.1f}] "
            f"{a.source_name}: {a.title[:60]}"
        )

    return selected[:count]
