/**
 * UFO DAILY — 前端脚本
 * 星空背景 / 数据加载 / 卡片渲染 / 筛选 / 搜索
 */

// ═══════════════════════════════════════════════════════════
// 1. 页面缩放 (1440px 设计基准)
// ═══════════════════════════════════════════════════════════
(function pageScale() {
  const DESIGN_W = 1440;
  const wrapper = document.getElementById('app-wrapper');
  function resize() {
    const scale = Math.min(window.innerWidth / DESIGN_W, 1);
    wrapper.style.transform = 'scale(' + scale + ')';
    wrapper.style.marginLeft = ((window.innerWidth - DESIGN_W * scale) / 2) + 'px';
    document.body.style.height = (wrapper.offsetHeight * scale) + 'px';
  }
  resize();
  window.addEventListener('resize', resize);
})();

// ═══════════════════════════════════════════════════════════
// 2. 星空背景动画
// ═══════════════════════════════════════════════════════════
(function initStarfield() {
  const canvas = document.getElementById('stars');
  const ctx = canvas.getContext('2d');
  let stars = [];
  const STAR_COUNT = 200;

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
    for (const s of stars) {
      s.twinkle += 0.015;
      const alpha = s.opacity * (0.6 + 0.4 * Math.sin(s.twinkle));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(180, 200, 255, ' + alpha + ')';
      ctx.fill();
      if (s.r > 1.2) {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(100, 150, 255, ' + (alpha * 0.15) + ')';
        ctx.fill();
      }
    }
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', function() { resize(); createStars(); });
  resize();
  createStars();
  draw();
})();

// ═══════════════════════════════════════════════════════════
// 3. 工具函数
// ═══════════════════════════════════════════════════════════
const NEWS_PATH = 'data/news.json';
const PLACEHOLDER_ICONS = ['🛸', '👽', '🌌', '🔭', '🪐', '☄️'];

function formatDate(iso) {
  try {
    var d = new Date(iso);
    var y = d.getFullYear();
    var M = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return y + '-' + M + '-' + dd;
  } catch(e) { return iso; }
}

function formatTime(iso) {
  try {
    var d = new Date(iso);
    var M = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var h = String(d.getHours()).padStart(2, '0');
    var m = String(d.getMinutes()).padStart(2, '0');
    return M + '-' + dd + ' · ' + h + ':' + m + ' UTC';
  } catch(e) { return ''; }
}

function classifyTag(article) {
  var text = (article.title_cn || article.title || '') + ' ' + (article.summary_cn || article.summary || '');
  if (/目击|目睹|拍到|拍摄|看见|sighting|witness|observed|spotted/i.test(text)) return 'sighting';
  if (/档案|解密|declassified|archive|FOIA|公开|文件|记录/i.test(text)) return 'declassified';
  return 'analysis';
}

function tagInfo(type) {
  switch(type) {
    case 'sighting': return { cls: 'red', text: '目击事件' };
    case 'declassified': return { cls: 'gold', text: '历史档案' };
    case 'analysis': return { cls: '', text: '深度分析' };
    default: return { cls: '', text: '深度分析' };
  }
}

// ═══════════════════════════════════════════════════════════
// 4. 全局数据
// ═══════════════════════════════════════════════════════════
var allArticles = [];
var currentFilter = 'all';

// ═══════════════════════════════════════════════════════════
// 5. 卡片渲染
// ═══════════════════════════════════════════════════════════
function createCard(article, idx) {
  var tag = tagInfo(classifyTag(article));
  var card = document.createElement('div');
  card.className = 'article-card';
  card.setAttribute('data-tag', classifyTag(article));
  card.style.animationDelay = (idx * 0.07) + 's';

  var hasImg = article.local_image && article.local_image.length > 0;
  var imgHTML = hasImg
    ? '<img src="' + article.local_image + '" alt="" loading="lazy">'
    : '<div class="card-image-placeholder">' + PLACEHOLDER_ICONS[idx % PLACEHOLDER_ICONS.length] + '</div>';

  card.innerHTML =
    '<div class="card-image">' + imgHTML + '</div>' +
    '<div class="card-content">' +
      '<div class="card-tags">' +
        '<span class="card-tag ' + tag.cls + '">' + tag.text + '</span>' +
        '<span class="card-source">' + (article.source_name || '未知来源') + '</span>' +
      '</div>' +
      '<h3 class="card-title">' + (article.title_cn || article.title) + '</h3>' +
      '<p class="card-summary">' + (article.summary_cn || article.summary || '') + '</p>' +
      '<div class="card-footer">' +
        '<span class="card-time">' + formatTime(article.published || article.updated) + '</span>' +
        '<span class="card-read">阅读全文 →</span>' +
      '</div>' +
    '</div>';

  card.addEventListener('click', function() {
    if (article.url && article.url !== '#') {
      window.open(article.url, '_blank', 'noopener');
    }
  });

  return card;
}

function renderCards(articles) {
  var grid = document.getElementById('articlesGrid');
  grid.innerHTML = '';
  articles.forEach(function(a, i) { grid.appendChild(createCard(a, i)); });
}

// ═══════════════════════════════════════════════════════════
// 6. 筛选
// ═══════════════════════════════════════════════════════════
function applyFilter(type) {
  currentFilter = type;
  var cards = document.querySelectorAll('.article-card');
  cards.forEach(function(c) {
    c.style.display = type === 'all' || c.getAttribute('data-tag') === type ? '' : 'none';
  });
}

document.addEventListener('DOMContentLoaded', function() {
  var pills = document.querySelectorAll('.filter-pill');
  pills.forEach(function(p) {
    p.addEventListener('click', function() {
      pills.forEach(function(x) { x.classList.remove('active'); });
      p.classList.add('active');
      applyFilter(p.getAttribute('data-filter') || 'all');
    });
  });
});

// ═══════════════════════════════════════════════════════════
// 7. 导航高亮
// ═══════════════════════════════════════════════════════════
(function navHighlight() {
  var sections = document.querySelectorAll('section[id]');
  var links = document.querySelectorAll('.nav-link');
  window.addEventListener('scroll', function() {
    var cur = '';
    sections.forEach(function(s) {
      if (window.scrollY >= s.offsetTop - 300) cur = s.id;
    });
    links.forEach(function(l) {
      l.classList.toggle('muted', l.getAttribute('href') !== '#' + cur);
    });
  });
})();

// ═══════════════════════════════════════════════════════════
// 8. 数据加载
// ═══════════════════════════════════════════════════════════
function loadNews() {
  var loadingEl = document.getElementById('loadingState');
  var errorEl = document.getElementById('errorState');
  var errorMsg = document.getElementById('errorMsg');

  fetch(NEWS_PATH)
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      if (!data.articles || !data.articles.length) throw new Error('暂无数据');

      allArticles = data.articles;
      if (loadingEl) loadingEl.style.display = 'none';

      // Hero badge
      document.getElementById('heroBadge').textContent = formatDate(data.updated) + ' 今日已更新';

      // Daily section
      document.getElementById('dailyTitle').textContent = '今日 ' + data.articles.length + ' 条发现';
      document.getElementById('dailyMeta').textContent = '更新于 06:00 · 源：Reddit r/UFOs、r/aliens、r/UFOscience、r/HighStrangeness、Space.com';

      // Archive meta
      document.getElementById('archiveMeta').textContent = '今日抓取 ' + data.articles.length + ' 条，AI 已全文翻译';

      // Data update time
      document.getElementById('dataUpdateTime').textContent = '上次更新：' + data.updated;
      document.getElementById('statToday').textContent = data.articles.length;

      // Render cards
      renderCards(data.articles);

      // Render archive rows
      renderArchive(data.articles);

      console.log('🛸 UFO DAILY: ' + data.articles.length + ' 条资讯已就绪 (' + data.date + ')');

      // Preload images
      data.articles.forEach(function(a) {
        if (a.local_image) { var img = new Image(); img.src = a.local_image; }
      });
    })
    .catch(function(e) {
      console.error('News load error:', e);
      if (loadingEl) loadingEl.style.display = 'none';
      if (errorEl) {
        errorEl.style.display = 'flex';
        errorMsg.textContent = '数据加载失败 — ' + (e.message || '未知错误');
      }
      document.getElementById('heroBadge').textContent = '数据加载中…';
      document.getElementById('dailyMeta').textContent = '请检查 data/news.json 文件';
    });
}

// ═══════════════════════════════════════════════════════════
// 9. Archive 表格渲染
// ═══════════════════════════════════════════════════════════
function renderArchive(articles) {
  var container = document.getElementById('archiveRows');
  var html = '';
  articles.forEach(function(a) {
    var tag = tagInfo(classifyTag(a));
    html +=
      '<div class="archive-row">' +
        '<span class="archive-row-date">' + formatDate(a.published || a.updated) + '</span>' +
        '<span class="archive-row-title">' + (a.title_cn || a.title) + '</span>' +
        '<span class="archive-row-source">' + (a.source_name || '') + '</span>' +
        '<span class="archive-row-tag ' + tag.cls + '">' + tag.text + '</span>' +
      '</div>';
  });
  container.innerHTML = html;

  // 点击行跳转原文
  container.querySelectorAll('.archive-row').forEach(function(row, i) {
    row.addEventListener('click', function() {
      var a = articles[i];
      if (a && a.url) window.open(a.url, '_blank', 'noopener');
    });
  });
}

// ═══════════════════════════════════════════════════════════
// 10. 搜索
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
  var input = document.getElementById('searchInput');
  if (!input) return;
  input.addEventListener('input', function() {
    var q = input.value.toLowerCase().trim();
    var rows = document.querySelectorAll('#archiveRows .archive-row');
    rows.forEach(function(row, i) {
      var show = !q;
      if (!show) {
        var text = row.textContent.toLowerCase();
        show = text.indexOf(q) !== -1;
      }
      row.style.display = show ? '' : 'none';
    });
  });
});

// ═══════════════════════════════════════════════════════════
// 启动
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', loadNews);
