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
    window.location.href = 'detail.html?id=' + article.id;
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
      document.getElementById('dailyMeta').textContent = '更新于 06:00 · 源：AARO/五角大楼 · NASA UAP · NUFORC · The Black Vault · GEIPAN · 英国国家档案馆';

      // Data update time
      document.getElementById('dataUpdateTime').textContent = '上次更新：' + data.updated;
      document.getElementById('statToday').textContent = data.articles.length;

      // Render cards
      renderCards(data.articles);

      // Load UK National Archives
      loadArchives();

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

var allArchives = [];
var archiveVisible = 36;
var archivesExpanded = false;

// ═══════════════════════════════════════════════════════════
// 9. 英国国家档案馆 UFO 档案加载与渲染
// ═══════════════════════════════════════════════════════════
var ARCHIVES_PATH = 'data/archives.json';

function createArchiveFileCard(file, idx) {
  var card = document.createElement('div');
  card.className = 'archive-file-card';
  if (idx >= archiveVisible) card.classList.add('hidden');
  card.setAttribute('data-archive-idx', idx);

  card.innerHTML =
    '<span class="archive-file-ref">' + (file.ref || '') + '</span>' +
    '<h4 class="archive-file-title">' + (file.title_cn || file.title_en) + '</h4>' +
    '<div class="archive-file-meta-row">' +
      '<span class="archive-file-date">' + (file.date || '') + '</span>' +
      '<span class="archive-file-pages">' + (file.size || '') + '</span>' +
      '<span class="archive-file-tag">' + (file.category || '档案') + '</span>' +
    '</div>' +
    '<div class="archive-file-bottom">' +
      '<span style="font-size:11px;color:var(--text-dim)">' + (file.title_en || '').substring(0, 35) + '…</span>' +
      '<a class="archive-file-dl-btn" href="' + (file.url || '#') + '" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="在英国国家档案馆 Discovery 查看并下载（免费注册账号）">' +
        '<span class="archive-file-dl-icon">📥</span> 查看 &amp; 下载' +
      '</a>' +
    '</div>';

  return card;
}

function renderArchives(files) {
  var grid = document.getElementById('archivesGrid');
  var loading = document.getElementById('archivesLoading');
  var moreWrap = document.getElementById('archivesMoreWrap');
  var moreBtn = document.getElementById('archivesMoreBtn');
  var gridExtra = document.getElementById('archivesGridExtra');

  // 隐藏加载
  if (loading) loading.style.display = 'none';

  // 渲染前 36 条到主网格
  grid.innerHTML = '';
  var visible = Math.min(files.length, archiveVisible);
  for (var i = 0; i < visible; i++) {
    grid.appendChild(createArchiveFileCard(files[i], i));
  }

  // 如果是 36 条之外有剩余
  if (files.length > archiveVisible) {
    if (moreWrap) moreWrap.style.display = 'flex';

    // 更新按钮文字
    var remaining = files.length - archiveVisible;
    if (moreBtn) {
      moreBtn.innerHTML = '展开更多档案 <span class="view-more-arrow" id="archivesMoreArrow">▼</span>（共 ' + remaining + ' 份）';
    }

    // 预渲染剩余条目到 extra 网格
    if (gridExtra) {
      gridExtra.innerHTML = '';
      for (var j = archiveVisible; j < files.length; j++) {
        gridExtra.appendChild(createArchiveFileCard(files[j], j));
      }
    }
  } else {
    if (moreWrap) moreWrap.style.display = 'none';
  }

  // 更新统计
  document.getElementById('archiveMeta').textContent =
    '共 ' + files.length + ' 份档案 · 来源: 英国国防部 DEFE 24 / DEFE 31 系列 · 可免费下载 PDF';
}

function toggleArchivesMore() {
  archivesExpanded = !archivesExpanded;
  var gridExtra = document.getElementById('archivesGridExtra');
  var btn = document.getElementById('archivesMoreBtn');
  var arrow = document.getElementById('archivesMoreArrow');

  if (archivesExpanded) {
    if (gridExtra) gridExtra.classList.add('expanded');
    if (btn) btn.innerHTML = '收起档案 <span class="view-more-arrow">▲</span>';
  } else {
    if (gridExtra) gridExtra.classList.remove('expanded');
    var remaining = allArchives.length - archiveVisible;
    if (btn) btn.innerHTML = '展开更多档案 <span class="view-more-arrow">▼</span>（共 ' + remaining + ' 份）';
  }
}

function searchArchives(query) {
  var cards = document.querySelectorAll('.archive-file-card');
  var queryLower = query.toLowerCase().trim();

  cards.forEach(function(card) {
    if (!queryLower) {
      // 显示：36 以内的显示，以外的根据展开状态
      var idx = parseInt(card.getAttribute('data-archive-idx'));
      if (idx < archiveVisible) {
        card.style.display = '';
      } else {
        card.style.display = archivesExpanded ? '' : 'none';
      }
    } else {
      var text = card.textContent.toLowerCase();
      card.style.display = text.indexOf(queryLower) !== -1 ? '' : 'none';
    }
  });

  // 搜索时隐藏/显示更多按钮
  var moreWrap = document.getElementById('archivesMoreWrap');
  if (moreWrap) {
    moreWrap.style.display = queryLower ? 'none' : (allArchives.length > archiveVisible ? 'flex' : 'none');
  }
}

function loadArchives() {
  fetch(ARCHIVES_PATH)
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      if (!data.files || !data.files.length) throw new Error('暂无档案数据');

      allArchives = data.files;
      renderArchives(allArchives);

      console.log('📁 UK Archives: ' + allArchives.length + ' 份 UFO 档案已就绪');
    })
    .catch(function(e) {
      console.error('Archives load error:', e);
      var loading = document.getElementById('archivesLoading');
      if (loading) {
        loading.innerHTML = '<p style="color:var(--text-tertiary)">档案数据加载失败 — ' + (e.message || '未知错误') + '</p>';
      }
    });
}

// 更多按钮事件
document.addEventListener('DOMContentLoaded', function() {
  var moreBtn = document.getElementById('archivesMoreBtn');
  if (moreBtn) {
    moreBtn.addEventListener('click', toggleArchivesMore);
  }

  // 搜索
  var searchInput = document.getElementById('archiveSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      searchArchives(searchInput.value);
    });
  }
});

// ═══════════════════════════════════════════════════════════
// 启动
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', loadNews);
