# 🛸 UFO 全球观测站

> **Global UFO Watch** — 每日最新 UFO/UAP 发现与深度分析，中文资讯聚合平台。

## 功能特性

- **每日自动更新**：北京时间 6:00 AM，GitHub Actions 自动抓取全球 UFO 最新资讯
- **多源聚合**：Reddit r/UFOs、r/aliens、r/UFOscience、r/HighStrangeness、Space.com 等权威来源
- **AI 翻译**：DeepSeek Chat API 将英文内容翻译为流畅中文
- **精选 6 条**：去重 + 评分算法，每天精选最有价值的 6 条
- **太空主题**：暗色星空背景、卡片式布局、响应式设计

## 项目结构

```
ufo-news/
├── .github/workflows/    # GitHub Actions 定时任务
├── scraper/              # Python 爬虫
│   ├── main.py           # 主流程
│   ├── sources.py        # 数据源配置
│   ├── translator.py     # DeepSeek 翻译
│   └── requirements.txt
├── site/                 # 静态网站（GitHub Pages）
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   ├── data/news.json    # 新闻数据
│   └── img/              # 图片素材
└── data/                 # 数据存档
    └── news.json
```

## 部署指南

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/ufo-news.git
cd ufo-news
```

### 2. 设置 DeepSeek API Key

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（[获取地址](https://platform.deepseek.com/api_keys)） |

### 3. 启用 GitHub Pages

Settings → Pages → Source: `Deploy from a branch` → Branch: `gh-pages` `/ (root)`

### 4. 手动触发首次运行

Actions → 🛸 UFO Daily Update → Run workflow

## 本地开发

```bash
# 安装依赖
pip install -r scraper/requirements.txt

# 运行爬虫（需要设置 DEEPSEEK_API_KEY 环境变量）
export DEEPSEEK_API_KEY="sk-xxx"
cd scraper && python main.py

# 本地预览网站
cd site && python -m http.server 8080
# 访问 http://localhost:8080
```

## 技术栈

| 层级 | 技术 |
|---|---|
| 爬虫 | Python · feedparser · BeautifulSoup4 · Pillow |
| 翻译 | DeepSeek Chat API (deepseek-chat) |
| 定时 | GitHub Actions (cron: `0 22 * * *` UTC) |
| 部署 | GitHub Pages (gh-pages branch) |
| 前端 | 原生 HTML/CSS/JS · Canvas 星空动效 |

## 许可证

MIT License — 数据来源于各公开平台的 RSS 订阅，版权归原作者所有。
