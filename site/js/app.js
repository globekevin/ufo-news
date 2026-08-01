/**
 * UFO 全球观测站 — 前端脚本
 * 星空背景 · 数据加载 · 卡片渲染
 */

// ═══════════════════════════════════════════════════════════
// 星空背景动画
// ═══════════════════════════════════════════════════════════

(function initStarfield() {
  const canvas = document.getElementById("stars");
  const ctx = canvas.getContext("2d");

  let stars = [];
  const STAR_COUNT = 150;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function createStars() {
    stars = [];
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.8 + 0.3,
        speed: Math.random() * 0.3 + 0.05,
        opacity: Math.random() * 0.8 + 0.2,
        twinkle: Math.random() * Math.PI * 2,
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (const star of stars) {
      star.twinkle += 0.015;
      const alpha = star.opacity * (0.6 + 0.4 * Math.sin(star.twinkle));

      ctx.beginPath();
      ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(180, 200, 255, ${alpha})`;
      ctx.fill();

      // 偶尔添加光晕
      if (star.r > 1.2) {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.r * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(100, 150, 255, ${alpha * 0.15})`;
        ctx.fill();
      }
    }
  }

  function animate() {
    draw();
    requestAnimationFrame(animate);
  }

  window.addEventListener("resize", () => {
    resize();
    createStars();
  });

  resize();
  createStars();
  animate();
})();

// ═══════════════════════════════════════════════════════════
// 数据加载与渲染
// ═══════════════════════════════════════════════════════════

const NEWS_DATA_PATH = "data/news.json";

// 图片占位符（无图时随机使用）
const PLACEHOLDER_ICONS = ["🛸", "👽", "🌌", "🔭", "🪐", "☄️", "🛰️", "⭐"];

function formatDate(isoString) {
  try {
    const d = new Date(isoString);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
    const wd = weekdays[d.getDay()];
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${year}年${month}月${day}日 周${wd} ${hours}:${minutes}`;
  } catch {
    return isoString;
  }
}

function getRelativeTime(isoString) {
  try {
    const then = new Date(isoString).getTime();
    const now = Date.now();
    const diff = now - then;
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return "刚刚";
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    return `${days} 天前`;
  } catch {
    return "";
  }
}

function createArticleCard(article, index) {
  const card = document.createElement("article");
  card.className = "article-card";
  card.style.animationDelay = `${index * 0.07}s`;

  const hasImage = article.local_image && article.local_image.length > 0;
  const placeholderIcon =
    PLACEHOLDER_ICONS[index % PLACEHOLDER_ICONS.length];

  card.innerHTML = `
    <div class="card-image">
      ${
        hasImage
          ? `<img src="${article.local_image}" alt="${article.title_cn}" loading="lazy">`
          : `<div class="card-image-placeholder">${placeholderIcon}</div>`
      }
      <span class="card-source">${article.source_name}</span>
    </div>
    <div class="card-body">
      <h2 class="card-title">${article.title_cn || article.title}</h2>
      <p class="card-summary">${article.summary_cn || article.summary}</p>
    </div>
    <div class="card-footer">
      <span class="card-meta">${getRelativeTime(article.published)}</span>
      <a href="${article.url}" target="_blank" rel="noopener noreferrer" class="card-link" onclick="event.stopPropagation()">
        阅读原文
      </a>
    </div>
  `;

  // 点击卡片跳转到原文
  card.addEventListener("click", () => {
    if (article.url && article.url !== "#") {
      window.open(article.url, "_blank", "noopener");
    }
  });

  return card;
}

function renderError(message) {
  const grid = document.getElementById("articlesGrid");
  grid.innerHTML = `
    <div class="error-state">
      <div class="error-icon">🛸</div>
      <p>${message || "数据加载失败，请稍后再试。"}</p>
      <p style="margin-top:8px;font-size:13px;">每日 6:00 AM (北京时间) 自动更新</p>
    </div>
  `;
}

async function loadNews() {
  const loadingEl = document.getElementById("loadingState");
  const updateTimeEl = document.getElementById("updateTime");
  const countEl = document.getElementById("articleCount");
  const overviewEl = document.getElementById("todayOverview");
  const overviewDateEl = document.getElementById("overviewDate");
  const grid = document.getElementById("articlesGrid");

  try {
    const resp = await fetch(NEWS_DATA_PATH);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (!data.articles || data.articles.length === 0) {
      throw new Error("今日数据为空");
    }

    // 移除加载状态
    if (loadingEl) loadingEl.remove();

    // 更新头部信息
    updateTimeEl.textContent = `更新于 ${formatDate(data.updated)}`;
    countEl.textContent = `今日 ${data.articles.length} 条`;

    // 显示今日概览
    overviewDateEl.textContent = data.date || data.updated.split("T")[0];
    overviewEl.style.display = "block";

    // 渲染卡片
    grid.innerHTML = "";
    data.articles.forEach((article, i) => {
      grid.appendChild(createArticleCard(article, i));
    });

    // 预加载图片
    data.articles.forEach((article) => {
      if (article.local_image) {
        const img = new Image();
        img.src = article.local_image;
      }
    });

    console.log(
      `🛸 UFO 观测站: 加载 ${data.articles.length} 条资讯 (${data.date})`
    );
  } catch (err) {
    console.error("News load error:", err);
    if (loadingEl) loadingEl.remove();
    renderError("数据加载失败 — 请检查 data/news.json 是否存在");
  }
}

// 启动
document.addEventListener("DOMContentLoaded", loadNews);
