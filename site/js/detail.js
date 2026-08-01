/**
 * UFO DAILY — 详情页脚本
 * 从 URL 参数获取文章 ID，动态渲染 Ardot 设计布局
 */

// ═══════════════════════════════════════════════════════════
// 1. 页面缩放 (1440px 设计基准)
// ═══════════════════════════════════════════════════════════
(function pageScale() {
  var DESIGN_W = 1440;
  var wrapper = document.getElementById('app-wrapper');
  function resize() {
    var scale = Math.min(window.innerWidth / DESIGN_W, 1);
    wrapper.style.transform = 'scale(' + scale + ')';
    wrapper.style.marginLeft = ((window.innerWidth - DESIGN_W * scale) / 2) + 'px';
    document.body.style.height = (wrapper.offsetHeight * scale) + 'px';
  }
  resize();
  window.addEventListener('resize', resize);
})();

// ═══════════════════════════════════════════════════════════
// 2. 工具函数
// ═══════════════════════════════════════════════════════════
var PLACEHOLDER_ICONS = ['🛸', '👽', '🌌', '🔭', '🪐', '☄️'];
var STOCK_IMAGES = [
  'assets/images/2_319-20260801_154220559.png',
  'assets/images/2_365-20260801_154220560.png',
  'assets/images/2_371-20260801_154220560.png',
  'assets/images/2_377-20260801_154220560.png'
];

function formatDate(iso) {
  try {
    var d = new Date(iso);
    var M = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var h = String(d.getHours()).padStart(2, '0');
    var m = String(d.getMinutes()).padStart(2, '0');
    return d.getFullYear() + '年' + M + '月' + dd + '日 ' + h + ':' + m + ' CST';
  } catch(e) { return iso; }
}

function formatDateShort(iso) {
  try {
    var d = new Date(iso);
    var M = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + M + '-' + dd;
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

function getUrlParam(name) {
  var params = new URLSearchParams(window.location.search);
  return params.get(name);
}

// ═══════════════════════════════════════════════════════════
// 3. 获取数据
// ═══════════════════════════════════════════════════════════
function loadArticle() {
  var articleId = getUrlParam('id');
  if (!articleId) {
    showError('缺少文章 ID', '请从首页点击文章卡片访问详情页');
    return;
  }

  fetch('data/news.json')
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      if (!data.articles || !data.articles.length) throw new Error('暂无数据');

      // Find article by ID
      var idx = -1;
      var article = null;
      for (var i = 0; i < data.articles.length; i++) {
        if (data.articles[i].id === articleId) {
          article = data.articles[i];
          idx = i;
          break;
        }
      }

      if (!article) {
        // Try numeric index fallback
        var numId = parseInt(articleId, 10);
        if (!isNaN(numId) && numId >= 0 && numId < data.articles.length) {
          article = data.articles[numId];
          idx = numId;
        }
      }

      if (!article) {
        showError('文章未找到', '该文章可能已被移除，或链接已失效');
        return;
      }

      renderArticle(article, idx, data.articles);
    })
    .catch(function(e) {
      console.error('Article load error:', e);
      showError('加载失败', e.message || '未知错误');
    });
}

function showError(title, note) {
  document.getElementById('loadingState').style.display = 'none';
  var errEl = document.getElementById('errorState');
  errEl.style.display = 'flex';
  document.getElementById('errorTitle').textContent = title;
  document.getElementById('errorNote').textContent = note;
}

// ═══════════════════════════════════════════════════════════
// 4. 渲染文章
// ═══════════════════════════════════════════════════════════
function renderArticle(article, idx, allArticles) {
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('articleContainer').style.display = 'block';

  var tag = tagInfo(classifyTag(article));
  var pubDate = formatDate(article.published || article.updated);

  // --- Hero Image ---
  var heroEl = document.getElementById('heroImage');
  var imgSrc = article.local_image || article.image_url || '';
  var hasValidImg = imgSrc && imgSrc.length > 0;
  if (hasValidImg) {
    heroEl.innerHTML = '<img src="' + imgSrc + '" alt="" onerror="this.parentElement.innerHTML=\'<div class=&quot;hero-img-fallback&quot;><span class=&quot;hero-img-icon&quot;>' + PLACEHOLDER_ICONS[idx % PLACEHOLDER_ICONS.length] + '</span></div>\'">';
  } else {
    var stockIdx = idx % STOCK_IMAGES.length;
    heroEl.innerHTML = '<img src="' + STOCK_IMAGES[stockIdx] + '" alt="">';
  }

  // --- Page Title ---
  document.title = (article.title_cn || article.title) + ' — UFO DAILY';

  // --- Meta ---
  var metaHTML = '<span class="meta-tag ' + tag.cls + '">' + tag.text + '</span>' +
    '<span class="meta-source">' + (article.source_name || '未知来源') + '</span>' +
    '<span class="meta-sep">·</span>' +
    '<span class="meta-date">' + pubDate + '</span>';
  document.getElementById('metaRow').innerHTML = metaHTML;

  // --- Title & Subtitle ---
  document.getElementById('articleTitle').textContent = article.title_cn || article.title;
  document.getElementById('articleSubtitle').textContent = article.summary_cn || '';
  document.getElementById('authorNote').textContent = 'AI 编译 & 翻译 · 来源: ' + (article.source_name || 'Reddit') + ' · ' + pubDate;

  // --- Body Content ---
  renderBodyContent(article);

  // --- Original English ---
  if (article.body) {
    var enBody = article.body;
    var enHTML = '<h2 class="body-heading">原文参考</h2>';
    // 正文分段
    var enParas = enBody.split(/\.(?=\s+[A-Z])|(?<=\.)\s+(?=[A-Z])/);
    for (var p = 0; p < enParas.length && p < 6; p++) {
      var para = enParas[p].trim();
      if (para.length > 5) {
        enHTML += '<p class="body-text-en">' + escapeHtml(para) + '</p>';
      }
    }
    document.getElementById('englishOriginal').innerHTML = enHTML;
    document.getElementById('englishOriginal').style.display = 'block';
  } else if (article.title && article.summary) {
    var enHTML = '<h2 class="body-heading">原文参考</h2>' +
      '<p class="body-text-en"><strong>' + escapeHtml(article.title) + '</strong></p>' +
      '<p class="body-text-en">' + escapeHtml(article.summary) + '</p>';
    document.getElementById('englishOriginal').innerHTML = enHTML;
    document.getElementById('englishOriginal').style.display = 'block';
  }

  // --- Source Card ---
  var srcCard = document.getElementById('sourceCard');
  srcCard.href = article.url || '#';
  var domain = '';
  try {
    var u = new URL(article.url);
    domain = u.hostname.replace('www.', '');
  } catch(e) { domain = article.source_name || '来源'; }
  var iconText = domain.split('.')[0].toUpperCase().substring(0, 4);
  document.getElementById('sourceIcon').textContent = iconText;
  document.getElementById('sourceUrlDisplay').textContent = domain + (article.url ? article.url.split(domain)[1] || '' : '');

  // --- Footer ---
  document.getElementById('footerCredits').textContent = '编译来源：' + (article.url || '—') + '  |  翻译：UFO DAILY 编辑部  |  发布时间：' + (article.published || article.updated || '—');
  var footerNext = document.getElementById('footerNext');
  if (idx < allArticles.length - 1) {
    footerNext.href = 'detail.html?id=' + allArticles[idx + 1].id;
    footerNext.style.display = '';
  } else {
    footerNext.style.display = 'none';
  }

  // --- Prev / Next ---
  setupNav(idx, allArticles);

  // --- Related ---
  renderRelated(idx, allArticles);
}

// ═══════════════════════════════════════════════════════════
// 5. Body 内容生成
// ═══════════════════════════════════════════════════════════
function renderBodyContent(article) {
  var container = document.getElementById('bodyContent');

  // 优先使用完整中文正文翻译
  var bodyCn = article.body_cn || '';
  if (bodyCn && bodyCn.length > 30) {
    var html = '';
    var paras = bodyCn.split(/\n+/).filter(function(p) { return p.trim().length > 0; });
    for (var i = 0; i < paras.length; i++) {
      html += '<p class="body-text">' + escapeHtml(paras[i].trim()) + '</p>';
    }
    // 如果内容够多，加引述
    if (paras.length > 3) {
      var midPara = paras[Math.floor(paras.length / 2)].trim();
      if (midPara.length > 20) {
        html += '<div class="pull-quote"><span class="quote-mark">"</span><span class="quote-text">' + escapeHtml(midPara.substring(0, 80)) + '</span></div>';
      }
    }
    container.innerHTML = html;
    return;
  }

  // 降级：用 summary_cn
  var text = article.summary_cn || article.summary || '';
  if (!text) {
    container.innerHTML = '<p class="body-text">暂无详细内容。</p>';
    return;
  }

  var sentences = text.split(/(?<=[。！？；\n])/g).filter(function(s) {
    return s.trim().length > 0;
  });

  var html = '';
  if (sentences.length <= 3) {
    html += '<p class="body-text">' + escapeHtml(sentences.join('')) + '</p>';
  } else {
    var firstGroup = sentences.slice(0, Math.min(3, sentences.length));
    html += '<p class="body-text">' + escapeHtml(firstGroup.join('')) + '</p>';
    if (sentences.length > 5) {
      html += '<h2 class="body-heading">关键详情</h2>';
    }
    var remaining = sentences.slice(Math.min(3, sentences.length));
    for (var i = 0; i < remaining.length; i += 3) {
      var group = remaining.slice(i, i + 3);
      html += '<p class="body-text">' + escapeHtml(group.join('')) + '</p>';
    }
    if (sentences.length > 6) {
      var quoteSentence = sentences[Math.floor(sentences.length / 2)].replace(/^[""]|[""]$/g, '').trim();
      if (quoteSentence.length > 10) {
        html += '<div class="pull-quote"><span class="quote-mark">"</span><span class="quote-text">' + escapeHtml(quoteSentence) + '</span></div>';
      }
    }
  }
  container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
// 6. 上一篇/下一篇
// ═══════════════════════════════════════════════════════════
function setupNav(idx, allArticles) {
  var prevLink = document.getElementById('prevLink');
  var nextLink = document.getElementById('nextLink');

  if (idx > 0) {
    prevLink.href = 'detail.html?id=' + allArticles[idx - 1].id;
    prevLink.style.visibility = 'visible';
  } else {
    prevLink.style.visibility = 'hidden';
  }

  if (idx < allArticles.length - 1) {
    nextLink.href = 'detail.html?id=' + allArticles[idx + 1].id;
    nextLink.style.visibility = 'visible';
  } else {
    nextLink.style.visibility = 'hidden';
  }
}

// ═══════════════════════════════════════════════════════════
// 7. 相关文章
// ═══════════════════════════════════════════════════════════
function renderRelated(idx, allArticles) {
  var grid = document.getElementById('relatedGrid');
  // Show 3 related articles (next 3, cycling around, excluding current)
  var related = [];
  for (var i = 1; i <= 3; i++) {
    var rIdx = (idx + i) % allArticles.length;
    if (rIdx !== idx) related.push(allArticles[rIdx]);
  }

  var html = '';
  var STOCK_REL = STOCK_IMAGES.slice(1).concat(STOCK_IMAGES[0]); // rotated for variety

  for (var j = 0; j < related.length; j++) {
    var a = related[j];
    var t = tagInfo(classifyTag(a));
    var imgPart = '';
    var stockImg = STOCK_REL[j % STOCK_REL.length];
    if (a.local_image || a.image_url) {
      imgPart = '<img src="' + (a.local_image || a.image_url) + '" alt="" loading="lazy" onerror="this.parentElement.innerHTML=\'<div class=&quot;rel-card-img-placeholder&quot;>' + PLACEHOLDER_ICONS[(idx + j) % PLACEHOLDER_ICONS.length] + '</div>\'">';
    } else {
      imgPart = '<img src="' + stockImg + '" alt="" loading="lazy">';
    }

    html += '<div class="rel-card" onclick="location.href=\'detail.html?id=' + a.id + '\'">' +
      '<div class="rel-card-img">' + imgPart + '</div>' +
      '<div class="rel-card-content">' +
        '<span class="rel-card-tag ' + t.cls + '">' + t.text + '</span>' +
        '<span class="rel-card-title">' + (a.title_cn || a.title) + '</span>' +
        '<span class="rel-card-date">' + formatDateShort(a.published || a.updated) + '</span>' +
      '</div>' +
    '</div>';
  }

  grid.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
// 8. 分享
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
  var shareLink = document.getElementById('shareLink');
  if (shareLink) {
    shareLink.addEventListener('click', function() {
      var url = window.location.href;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function() {
          shareLink.textContent = '已复制 ✓';
          setTimeout(function() { shareLink.textContent = '分享'; }, 2000);
        }).catch(function() {
          prompt('复制链接:', url);
        });
      } else {
        prompt('复制链接:', url);
      }
    });
  }
});

// ═══════════════════════════════════════════════════════════
// 9. HTML 转义
// ═══════════════════════════════════════════════════════════
function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════
// 启动
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', loadArticle);
