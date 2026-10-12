/**
 * IntelliRec — Web Content Intelligence & Recommendation Engine
 * Core Frontend Reactive Client & ASTMA Analytics Visualization
 */

let token = localStorage.getItem('ir_token');
let me = null;
let currentArticleId = null;
let currentArticleData = null;
let charts = {};
let activeCategoryFilter = 'All';

const POPULAR_INTERESTS = [
  "AI", "Data Science", "Machine Learning", "Cloud",
  "Cybersecurity", "Social Analytics", "NLP", "Web Development",
  "Enterprise Systems", "Project Management", "Business", "Media Analytics"
];

// Utility: Element selector
const $ = (id) => document.getElementById(id);

// Utility: Toast notification
function toast(msg, isError = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = (isError ? '⚠️ ' : '✓ ') + msg;
  el.style.display = 'flex';
  el.style.backgroundColor = isError ? '#e11d48' : '#0f172a';
  setTimeout(() => {
    el.style.display = 'none';
  }, 2600);
}

// Utility: HTML Escaping
function escapeHtml(s = '') {
  if (typeof s !== 'string') return '';
  return s.replace(/[&<>'"]/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[c]));
}

// Utility: Generic API fetch wrapper
async function api(path, opt = {}) {
  opt.headers = Object.assign({ 'Content-Type': 'application/json' }, opt.headers || {});
  if (token) {
    opt.headers.Authorization = 'Bearer ' + token;
  }
  
  const res = await fetch(path, opt);
  if (res.status === 401) {
    token = null;
    localStorage.removeItem('ir_token');
    showAuthModal();
    throw new Error('Session expired. Please sign in again.');
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'API request failed');
  }
  return data;
}

// ============================================================
// THEME MANAGEMENT
// ============================================================
function toggleTheme() {
  document.body.classList.toggle('dark');
  const isDark = document.body.classList.contains('dark');
  localStorage.setItem('ir_theme', isDark ? 'dark' : 'light');
  if (charts.social) loadAdmin(); // re-draw charts with adapted contrast
}

function initTheme() {
  if (localStorage.getItem('ir_theme') === 'dark') {
    document.body.classList.add('dark');
  }
}

// ============================================================
// APPLICATION BOOTSTRAP
// ============================================================
async function initApp() {
  initTheme();
  
  if (!token) {
    showAuthModal();
    return;
  }

  try {
    me = await api('/api/v1/auth/me');
    updateUserUI();
    
    // Check URL hash for routing
    const initialView = location.hash ? location.hash.replace('#', '') : 'home';
    loadView(initialView);
  } catch (err) {
    console.warn('Initialization failed:', err);
    showAuthModal();
  }
}

function updateUserUI() {
  if (!me) return;
  const initial = me.name ? me.name[0].toUpperCase() : 'U';
  
  if ($('sideName')) $('sideName').textContent = me.name;
  if ($('sideRole')) $('sideRole').textContent = me.role;
  if ($('sideAvatar')) $('sideAvatar').textContent = initial;
  if ($('profileBigAvatar')) $('profileBigAvatar').textContent = initial;
  if ($('profileFullName')) $('profileFullName').textContent = me.name;
  if ($('profileEmailText')) $('profileEmailText').textContent = me.email;
  if ($('profileRoleBadge')) $('profileRoleBadge').textContent = me.role;
  
  // Show Admin link in sidebar if admin
  if ($('adminNavItem')) {
    $('adminNavItem').style.display = me.role === 'ADMIN' ? 'flex' : 'none';
  }

  // Set greeting according to time of day
  const hour = new Date().getHours();
  let greet = "Good evening";
  if (hour < 12) greet = "Good morning";
  else if (hour < 18) greet = "Good afternoon";
  
  if ($('pageGreeting')) {
    $('pageGreeting').textContent = `${greet}, ${me.name.split(' ')[0]} 👋`;
  }
}

// ============================================================
// VIEW NAVIGATION & ROUTING
// ============================================================
function loadView(viewName) {
  const allowed = ['home', 'feed', 'trending', 'saved', 'activity', 'nlp', 'profile', 'admin'];
  if (!allowed.includes(viewName)) viewName = 'home';
  if (viewName === 'admin' && me && me.role !== 'ADMIN') viewName = 'home';

  // Toggle active view panel
  document.querySelectorAll('.view-panel').forEach((el) => el.classList.add('hidden'));
  const target = $('view-' + viewName);
  if (target) target.classList.remove('hidden');

  // Toggle sidebar active item
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

  // Update URL hash
  location.hash = '#' + viewName;

  // Load specific view data
  if (viewName === 'home') loadHome();
  else if (viewName === 'feed') loadFeed();
  else if (viewName === 'trending') loadTrending();
  else if (viewName === 'saved') loadSaved();
  else if (viewName === 'activity') loadActivity();
  else if (viewName === 'profile') loadProfile();
  else if (viewName === 'admin') loadAdmin();
}

function toggleSidebar() {
  const sb = $('sidebar');
  if (sb) sb.classList.toggle('open');
}

// ============================================================
// DATA LOADERS FOR VIEWS
// ============================================================

// --- 1. OVERVIEW / HOME ---
async function loadHome() {
  try {
    const [recs, allContent] = await Promise.all([
      api('/api/v1/recommendations?k=6'),
      api('/api/v1/content?limit=50'),
    ]);

    renderCards($('homeFeedGrid'), recs.slice(0, 6));

    const trending = await api('/api/v1/trending?k=3');
    renderCards($('homeTrendingGrid'), trending, true);

    if ($('kpiContentCount')) $('kpiContentCount').textContent = allContent.length;
    if ($('homeUserInterestsCount')) $('homeUserInterestsCount').textContent = (me.interests || []).length;
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 2. FOR YOU FEED ---
async function loadFeed() {
  try {
    const typeFilter = $('feedTypeFilter') ? $('feedTypeFilter').value : 'All';
    let url = `/api/v1/recommendations?k=18`;
    if (activeCategoryFilter !== 'All') {
      url += `&category=${encodeURIComponent(activeCategoryFilter)}`;
    }
    if (typeFilter !== 'All') {
      url += `&content_type=${encodeURIComponent(typeFilter)}`;
    }

    const recs = await api(url);
    renderCards($('feedGrid'), recs);
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 3. TRENDING INTELLIGENCE ---
async function loadTrending() {
  try {
    const trendItems = await api('/api/v1/trending?k=12');
    renderCards($('trendingGrid'), trendItems, true);
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 4. SAVED BOOKMARKS ---
async function loadSaved() {
  try {
    const savedItems = await api('/api/v1/users/saved');
    renderCards($('savedGrid'), savedItems);
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 5. MY ACTIVITY TIMELINE ---
async function loadActivity() {
  try {
    const activities = await api('/api/v1/users/activity');
    const container = $('activityTimeline');
    if (!container) return;

    if (!activities.length) {
      container.innerHTML = `
        <div style="background: var(--bg-surface); padding: 32px; text-align: center; border-radius: var(--radius-lg); border: 1px solid var(--border-color); color: var(--text-muted);">
          No interactions recorded yet. Explore and read articles in the feed to build your activity profile!
        </div>
      `;
      return;
    }

    const actionIcons = {
      view: '👁️ Read',
      like: '❤️ Liked',
      save: '🔖 Saved',
      share: '↗ Shared',
      comment: '💬 Commented',
    };

    container.innerHTML = activities.map((a) => {
      const icon = actionIcons[a.kind] || '⚡ Interacted';
      const dateStr = a.created_at ? new Date(a.created_at).toLocaleString() : '';
      return `
        <div class="kpi-card" style="padding: 16px 20px;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
              <span class="pill" style="font-size: 10px;">${escapeHtml(a.category)}</span>
              <b style="font-size: 15px; cursor: pointer; color: var(--primary);" onclick="openArticleModal(${a.content_id})">
                ${escapeHtml(a.title)}
              </b>
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
              ${icon} ${a.duration_seconds > 0 ? `(${a.duration_seconds}s dwell time)` : ''} • ${dateStr}
            </div>
          </div>
          <button class="card-btn" onclick="openArticleModal(${a.content_id})">Open Article →</button>
        </div>
      `;
    }).join('');
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 6. USER PROFILE & INTERESTS ---
function loadProfile() {
  if (!me) return;
  const userInterests = new Set(me.interests || []);
  const cloud = $('availableInterestsCloud');
  if (!cloud) return;

  cloud.innerHTML = POPULAR_INTERESTS.map((tag) => {
    const active = userInterests.has(tag);
    return `
      <button class="category-chip ${active ? 'active' : ''}" onclick="toggleProfileInterest('${escapeHtml(tag)}')">
        ${active ? '✓ ' : '+ '}${escapeHtml(tag)}
      </button>
    `;
  }).join('');
}

function toggleProfileInterest(tag) {
  if (!me) return;
  me.interests = me.interests || [];
  const idx = me.interests.indexOf(tag);
  if (idx > -1) {
    me.interests.splice(idx, 1);
  } else {
    me.interests.push(tag);
  }
  loadProfile();
}

function addCustomInterest() {
  const input = $('customInterestInput');
  const val = input.value.trim();
  if (!val) return;
  if (!me.interests.includes(val)) {
    me.interests.push(val);
  }
  input.value = '';
  loadProfile();
}

async function saveUserInterests() {
  try {
    const res = await api('/api/v1/users/interests', {
      method: 'PUT',
      body: JSON.stringify({ interests: me.interests || [] }),
    });
    me.interests = res.interests;
    toast('Interests updated & recommendation engine recalibrated!');
    loadHome();
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 7. NLP LAB ---
function setNlpSample(type) {
  const samples = {
    positive: "Generative AI and modern LLMs demonstrate phenomenal productivity gains and remarkable contextual fluency across enterprise codebases.",
    neutral: "The REST API architecture specifies stateless communication, deterministic HTTP endpoints, and JSON response models.",
    critical: "The database query latency is completely unacceptable during peak traffic bursts, causing cascading timeouts and degraded user experience.",
  };
  if ($('nlpInputText')) {
    $('nlpInputText').value = samples[type] || '';
  }
}

async function runNlpAnalysis() {
  const text = $('nlpInputText').value.trim();
  if (!text) return toast('Please enter some text to analyze', true);

  try {
    const res = await api('/api/v1/analytics/text/analyze', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });

    const s = res.sentiment;
    const compound = s.compound;
    // Map -1.0 to 1.0 -> 0% to 100%
    const gaugePct = Math.min(100, Math.max(0, ((compound + 1.0) / 2.0) * 100));

    $('nlpResultsContent').innerHTML = `
      <div style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <b style="font-size: 15px;">VADER Sentiment Polarity</b>
          <span class="sentiment-badge ${s.label}">${s.label.toUpperCase()} (${compound > 0 ? '+' : ''}${compound})</span>
        </div>
        <div class="sentiment-meter-gauge">
          <div class="gauge-pin" style="left: ${gaugePct}%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted);">
          <span>Negative: ${(s.neg * 100).toFixed(1)}%</span>
          <span>Neutral: ${(s.neu * 100).toFixed(1)}%</span>
          <span>Positive: ${(s.pos * 100).toFixed(1)}%</span>
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <b style="font-size: 14px;">Extracted TF-IDF Feature Keywords:</b>
        <div class="keywords-tag-cloud">
          ${(res.keywords || []).map((k) => `<span class="keyword-tag">#${escapeHtml(k)}</span>`).join('') || '<span style="color:var(--text-muted);font-size:13px;">No prominent keywords extracted</span>'}
        </div>
      </div>

      <div>
        <b style="font-size: 14px;">Predicted NMF Semantic Topic:</b>
        <div style="margin-top: 8px; padding: 12px; border-radius: var(--radius-sm); background: var(--bg-subtle); border: 1px solid var(--border-color); font-size: 13px;">
          <b>Cluster Topic #${res.predicted_topic.index}</b>
          <div style="color: var(--text-muted); margin-top: 4px;">
            Top Terms: ${(res.predicted_topic.terms || []).join(' • ')}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    toast(err.message, true);
  }
}

// --- 8. ADMIN COMMAND CENTER ---
async function loadAdmin() {
  if (!me || me.role !== 'ADMIN') return;

  try {
    const [overview, social, textData, media, users, allContent] = await Promise.all([
      api('/api/v1/analytics/overview'),
      api('/api/v1/analytics/social'),
      api('/api/v1/analytics/text'),
      api('/api/v1/analytics/media'),
      api('/api/v1/admin/users'),
      api('/api/v1/content?limit=100'),
    ]);

    // Admin KPIs
    $('adminKpisGrid').innerHTML = `
      <div class="kpi-card">
        <div>
          <div class="kpi-label">Total Users</div>
          <div class="kpi-val">${overview.users}</div>
        </div>
        <div class="kpi-icon">👥</div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-label">Total Content</div>
          <div class="kpi-val">${overview.content}</div>
        </div>
        <div class="kpi-icon">📄</div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-label">Total Views</div>
          <div class="kpi-val">${overview.views}</div>
        </div>
        <div class="kpi-icon">👁️</div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-label">Avg Engagement</div>
          <div class="kpi-val">${overview.engagement_rate}%</div>
        </div>
        <div class="kpi-icon">📈</div>
      </div>
    `;

    // Social Bar Chart
    drawBarChart(
      'chartSocial',
      social.map((s) => s.category),
      [
        {
          label: 'Views',
          data: social.map((s) => s.views),
          backgroundColor: '#6366f1',
        },
        {
          label: 'Likes',
          data: social.map((s) => s.likes),
          backgroundColor: '#f43f5e',
        },
      ]
    );

    // Comment Sentiment Doughnut
    drawDoughnutChart(
      'chartSentiment',
      textData.comment_sentiment.map((c) => c.label.toUpperCase()),
      textData.comment_sentiment.map((c) => c.count),
      ['#10b981', '#f59e0b', '#f43f5e']
    );

    // Media Chart
    drawBarChart(
      'chartMedia',
      media.map((m) => m.type.toUpperCase()),
      [
        {
          label: 'Item Count',
          data: media.map((m) => m.items),
          backgroundColor: '#06b6d4',
        },
        {
          label: 'Avg Watch Time (s)',
          data: media.map((m) => m.avg_watch_seconds),
          backgroundColor: '#8b5cf6',
        },
      ]
    );

    // Discovered Topics List
    $('adminTopicsList').innerHTML = (textData.topics || []).map((t) => `
      <div style="background: var(--bg-subtle); padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); font-size: 13px;">
        <b style="color: var(--primary);">Topic #${t.topic}:</b>
        <span style="color: var(--text-muted); margin-left: 6px;">${t.keywords.join(' • ')}</span>
      </div>
    `).join('') || '<div style="color: var(--text-muted);">No topics computed.</div>';

    // Content Management Table
    $('adminContentTableBody').innerHTML = allContent.map((c) => `
      <tr>
        <td><b>#${c.id}</b></td>
        <td><span style="cursor:pointer; font-weight:600; color:var(--primary);" onclick="openArticleModal(${c.id})">${escapeHtml(c.title)}</span></td>
        <td><span class="pill" style="font-size:10px;">${escapeHtml(c.category)}</span></td>
        <td>${escapeHtml(c.content_type)}</td>
        <td>${c.views}</td>
        <td>${c.likes}</td>
        <td><span class="sentiment-badge ${c.sentiment_label}">${c.sentiment_label}</span></td>
        <td>
          <button class="btn sm danger" onclick="deleteContentItem(${c.id})">Delete</button>
        </td>
      </tr>
    `).join('');

    // Users Management Table
    $('adminUsersTableBody').innerHTML = users.map((u) => `
      <tr>
        <td>#${u.id}</td>
        <td><b>${escapeHtml(u.name)}</b></td>
        <td>${escapeHtml(u.email)}</td>
        <td><span class="pill" style="font-size:10px;">${u.role}</span></td>
        <td>${u.is_active ? '<span style="color:#10b981;font-weight:700;">Active</span>' : '<span style="color:#f43f5e;font-weight:700;">Disabled</span>'}</td>
        <td style="font-size:12px; color:var(--text-muted);">${u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
        <td>
          <button class="btn sm ghost" onclick="toggleUserStatus(${u.id}, ${!u.is_active})">
            ${u.is_active ? 'Deactivate' : 'Activate'}
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    toast(err.message, true);
  }
}

async function retrainEngine() {
  const btn = $('retrainBtn');
  if (btn) btn.disabled = true;
  try {
    const res = await api('/api/v1/admin/retrain', { method: 'POST' });
    toast(res.message || 'Engine retrained successfully!');
    loadAdmin();
  } catch (err) {
    toast(err.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function deleteContentItem(cid) {
  if (!confirm(`Are you sure you want to delete content #${cid}?`)) return;
  try {
    await api(`/api/v1/content/${cid}`, { method: 'DELETE' });
    toast('Content item removed');
    loadAdmin();
  } catch (err) {
    toast(err.message, true);
  }
}

async function toggleUserStatus(uid, newStatus) {
  try {
    await api(`/api/v1/admin/users/${uid}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: newStatus }),
    });
    toast(`User status updated to ${newStatus ? 'Active' : 'Disabled'}`);
    loadAdmin();
  } catch (err) {
    toast(err.message, true);
  }
}

// ============================================================
// CONTENT CARD RENDERING
// ============================================================
function renderCards(container, items, isTrending = false) {
  if (!container) return;
  if (!items || !items.length) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; background: var(--bg-surface); padding: 40px; text-align: center; border-radius: var(--radius-lg); border: 1px solid var(--border-color); color: var(--text-muted);">
        <p style="font-size: 16px; font-weight: 600; margin-bottom: 6px;">No articles found</p>
        <p style="font-size: 13px;">Try switching filters or adjusting your profile interests.</p>
      </div>
    `;
    return;
  }

  const formatIcons = { article: '📄 Article', video: '🎬 Video', image: '🖼️ Visual' };

  container.innerHTML = items.map((item) => {
    const imgUrl = item.image_url || 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80';
    const sLabel = item.sentiment_label || 'neutral';
    const isLiked = Boolean(item.is_liked);
    const isSaved = Boolean(item.is_saved);

    // Explainability info
    let whyHtml = '';
    if (item.why && item.why.reasons && item.why.reasons.length) {
      whyHtml = `
        <div class="card-why-box">
          <div class="why-header">
            <span>🧠 Explainable AI Match</span>
            ${item.score ? `<span>Score: ${(item.score * 100).toFixed(0)}%</span>` : ''}
          </div>
          <div class="why-reasons-list">
            • ${escapeHtml(item.why.reasons[0])}
          </div>
        </div>
      `;
    }

    return `
      <article class="content-card">
        <div class="card-image-wrap" onclick="openArticleModal(${item.id})" style="cursor: pointer;">
          <img src="${escapeHtml(imgUrl)}" alt="${escapeHtml(item.title)}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80'">
          <div class="card-badges-float">
            <span class="pill">${formatIcons[item.content_type] || '📄 Content'}</span>
            <span class="pill" style="background: rgba(15,23,42,0.8); color: #fff;">${escapeHtml(item.category)}</span>
            ${isTrending && item.rank ? `<span class="pill" style="background:#f59e0b; color:#fff;">🔥 #${item.rank}</span>` : ''}
          </div>
        </div>

        <div class="card-body">
          <div class="card-meta-top">
            <span>By ${escapeHtml(item.author || 'IntelliRec')}</span>
            <span class="sentiment-badge ${sLabel}">${sLabel}</span>
          </div>

          <h3 onclick="openArticleModal(${item.id})">${escapeHtml(item.title)}</h3>
          <p>${escapeHtml(item.body.slice(0, 140))}...</p>

          ${whyHtml}

          <div class="card-stats">
            <span>👁️ ${item.views}</span>
            <span>❤️ <b id="card-like-${item.id}">${item.likes}</b></span>
            <span>💬 ${item.comments || 0}</span>
            <span>↗ ${item.shares || 0}</span>
          </div>

          <div class="card-actions">
            <button class="card-btn ${isLiked ? 'active-like' : ''}" id="like-btn-${item.id}" onclick="handleCardInteraction(${item.id}, 'like')">
              ❤️ ${isLiked ? 'Liked' : 'Like'}
            </button>
            <button class="card-btn ${isSaved ? 'active-save' : ''}" id="save-btn-${item.id}" onclick="handleCardInteraction(${item.id}, 'save')">
              🔖 ${isSaved ? 'Saved' : 'Save'}
            </button>
            <button class="card-btn primary-read" onclick="openArticleModal(${item.id})">
              Read →
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

// ============================================================
// INTERACTIONS & FEEDBACK HANDLERS
// ============================================================
async function handleCardInteraction(cid, kind) {
  try {
    const res = await api('/api/v1/interactions', {
      method: 'POST',
      body: JSON.stringify({ content_id: cid, kind, duration_seconds: 0 }),
    });

    const likeBtn = $(`like-btn-${cid}`);
    const saveBtn = $(`save-btn-${cid}`);
    const likeCounter = $(`card-like-${cid}`);

    if (kind === 'like') {
      const isNowLiked = res.action === 'added';
      if (likeBtn) {
        likeBtn.classList.toggle('active-like', isNowLiked);
        likeBtn.innerHTML = `❤️ ${isNowLiked ? 'Liked' : 'Like'}`;
      }
      if (likeCounter) likeCounter.textContent = res.likes;
    } else if (kind === 'save') {
      const isNowSaved = res.action === 'added';
      if (saveBtn) {
        saveBtn.classList.toggle('active-save', isNowSaved);
        saveBtn.innerHTML = `🔖 ${isNowSaved ? 'Saved' : 'Save'}`;
      }
      toast(isNowSaved ? 'Saved to bookmarks' : 'Removed from bookmarks');
    }
  } catch (err) {
    toast(err.message, true);
  }
}

async function sendFeedback(feedbackType) {
  if (!currentArticleId) return;
  try {
    await api('/api/v1/recommendations/feedback', {
      method: 'POST',
      body: JSON.stringify({ content_id: currentArticleId, feedback: feedbackType }),
    });
    toast(`Feedback recorded: Engine tuned for ${feedbackType === 'liked' ? 'more' : 'fewer'} similar topics!`);
  } catch (err) {
    toast(err.message, true);
  }
}

// ============================================================
// ARTICLE DETAIL / READER MODAL
// ============================================================
async function openArticleModal(cid) {
  try {
    currentArticleId = cid;
    
    // Fetch article, explanation, comments, and similar items concurrently
    const [item, explanation, comments, similar] = await Promise.all([
      api(`/api/v1/content/${cid}`),
      api(`/api/v1/recommendations/explain/${cid}`).catch(() => null),
      api(`/api/v1/content/${cid}/comments`),
      api(`/api/v1/content/${cid}/similar`),
    ]);

    currentArticleData = item;

    // Record 'view' interaction
    api('/api/v1/interactions', {
      method: 'POST',
      body: JSON.stringify({ content_id: cid, kind: 'view', duration_seconds: 30 }),
    }).catch(() => {});

    // Populate modal UI
    if ($('modalCategoryBadge')) $('modalCategoryBadge').textContent = item.category;
    if ($('modalArticleTitle')) $('modalArticleTitle').textContent = item.title;
    if ($('modalArticleAuthor')) $('modalArticleAuthor').textContent = `By ${item.author || 'IntelliRec'}`;
    if ($('modalArticleDate')) $('modalArticleDate').textContent = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Published recently';
    
    const heroImg = $('modalHeroImg');
    if (heroImg) {
      if (item.image_url) {
        heroImg.src = item.image_url;
        heroImg.style.display = 'block';
      } else {
        heroImg.style.display = 'none';
      }
    }

    const sentBadge = $('modalSentimentBadge');
    if (sentBadge) {
      sentBadge.className = `sentiment-badge ${item.sentiment_label}`;
      sentBadge.textContent = `${item.sentiment_label.toUpperCase()} (${item.sentiment > 0 ? '+' : ''}${item.sentiment})`;
    }

    // Body with paragraphs
    const bodyContainer = $('modalArticleContent');
    if (bodyContainer) {
      const paragraphs = item.body.split('\n\n').filter(Boolean);
      bodyContainer.innerHTML = paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join('');
    }

    // Explainability Panel
    const signalsGrid = $('modalSignalsGrid');
    const reasonsList = $('modalReasonsList');
    if (explanation && explanation.why) {
      const w = explanation.why;
      if (signalsGrid) {
        signalsGrid.innerHTML = `
          <div class="signal-metric-box">
            <b>${(w.content * 100).toFixed(0)}%</b>
            <small>Content Vector</small>
          </div>
          <div class="signal-metric-box">
            <b>${(w.collaborative * 100).toFixed(0)}%</b>
            <small>Collab Matrix</small>
          </div>
          <div class="signal-metric-box">
            <b>${(w.popularity * 100).toFixed(0)}%</b>
            <small>Popularity</small>
          </div>
          <div class="signal-metric-box">
            <b>${(w.recency * 100).toFixed(0)}%</b>
            <small>Recency</small>
          </div>
          <div class="signal-metric-box">
            <b>${(w.feedback * 100).toFixed(0)}%</b>
            <small>Feedback</small>
          </div>
        `;
      }
      if (reasonsList && w.reasons) {
        reasonsList.innerHTML = w.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('');
      }
    }

    // Render Comments
    renderModalComments(comments);

    // Render Similar Content
    renderCards($('modalSimilarGrid'), similar);

    // Open Modal
    $('articleModal').classList.add('open');
  } catch (err) {
    toast(err.message, true);
  }
}

function closeArticleModal() {
  $('articleModal').classList.remove('open');
  currentArticleId = null;
  currentArticleData = null;
}

function renderModalComments(comments) {
  const container = $('modalCommentsList');
  if (!container) return;

  if (!comments.length) {
    container.innerHTML = `<div style="color:var(--text-muted); font-size:13.5px;">No comments yet. Be the first to share an insight!</div>`;
    return;
  }

  container.innerHTML = comments.map((c) => `
    <div class="comment-bubble">
      <div class="comment-author-row">
        <b>${escapeHtml(c.user_name || 'Community Member')}</b>
        <span class="sentiment-badge ${c.sentiment_label}">${c.sentiment_label} (${c.sentiment > 0 ? '+' : ''}${c.sentiment})</span>
      </div>
      <p>${escapeHtml(c.text)}</p>
    </div>
  `).join('');
}

async function submitComment() {
  if (!currentArticleId) return;
  const input = $('newCommentInput');
  const text = input.value.trim();
  if (!text) return toast('Please enter a comment', true);

  try {
    const res = await api('/api/v1/comments', {
      method: 'POST',
      body: JSON.stringify({ content_id: currentArticleId, text }),
    });

    input.value = '';
    toast(`Comment posted! Sentiment classified as ${res.sentiment_label}`);

    // Reload comments
    const updated = await api(`/api/v1/content/${currentArticleId}/comments`);
    renderModalComments(updated);
  } catch (err) {
    toast(err.message, true);
  }
}

function handleModalLike() {
  if (!currentArticleId) return;
  handleCardInteraction(currentArticleId, 'like');
}

function handleModalSave() {
  if (!currentArticleId) return;
  handleCardInteraction(currentArticleId, 'save');
}

function handleShareCurrentArticle() {
  if (!currentArticleId) return;
  const shareUrl = `${location.origin}/app#feed`;
  navigator.clipboard.writeText(shareUrl).then(() => {
    toast('Article link copied to clipboard!');
  }).catch(() => {
    toast('Link ready to share!');
  });
  api('/api/v1/interactions', {
    method: 'POST',
    body: JSON.stringify({ content_id: currentArticleId, kind: 'share', duration_seconds: 0 }),
  }).catch(() => {});
}

// ============================================================
// SEARCH & FILTERING
// ============================================================
function filterCategory(cat) {
  activeCategoryFilter = cat;
  document.querySelectorAll('.category-chip').forEach((c) => {
    c.classList.toggle('active', c.textContent.trim().includes(cat) || (cat === 'All' && c.textContent.includes('All')));
  });
  loadFeed();
}

async function handleSearch() {
  const query = $('searchInput').value.trim();
  if (!query) return;

  try {
    loadView('feed');
    const results = await api(`/api/v1/content?search=${encodeURIComponent(query)}&limit=30`);
    renderCards($('feedGrid'), results);
  } catch (err) {
    toast(err.message, true);
  }
}

// ============================================================
// ADMIN: ADD CONTENT MODAL
// ============================================================
function openAddContentModal() {
  $('addContentModal').classList.add('open');
}

function closeAddContentModal() {
  $('addContentModal').classList.remove('open');
}

async function submitNewContent() {
  const title = $('addTitle').value.trim();
  const category = $('addCategory').value.trim();
  const content_type = $('addType').value;
  const author = $('addAuthor').value.trim() || 'IntelliRec Editorial';
  const image_url = $('addImageUrl').value.trim() || null;
  const body = $('addBody').value.trim();

  try {
    await api('/api/v1/content', {
      method: 'POST',
      body: JSON.stringify({ title, category, content_type, author, image_url, body }),
    });
    toast('Content successfully published!');
    closeAddContentModal();
    loadAdmin();
  } catch (err) {
    toast(err.message, true);
  }
}

// ============================================================
// CHART.JS HELPERS
// ============================================================
function drawBarChart(canvasId, labels, datasets) {
  const el = $(canvasId);
  if (!el) return;
  if (charts[canvasId]) charts[canvasId].destroy();

  const isDark = document.body.classList.contains('dark');
  const textColor = isDark ? '#94a3b8' : '#64748b';

  charts[canvasId] = new Chart(el, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor } },
      },
      scales: {
        x: { ticks: { color: textColor }, grid: { display: false } },
        y: { ticks: { color: textColor }, grid: { color: isDark ? '#1e293b' : '#f1f5f9' } },
      },
    },
  });
}

function drawDoughnutChart(canvasId, labels, data, colors) {
  const el = $(canvasId);
  if (!el) return;
  if (charts[canvasId]) charts[canvasId].destroy();

  const isDark = document.body.classList.contains('dark');
  const textColor = isDark ? '#94a3b8' : '#64748b';

  charts[canvasId] = new Chart(el, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: textColor } },
      },
    },
  });
}

// ============================================================
// AUTHENTICATION MODAL & DEMO LOGINS
// ============================================================
function showAuthModal() {
  document.body.innerHTML = `
    <div id="toast"></div>
    <div class="auth-wrapper">
      <div class="auth-card">
        <div class="brand" style="justify-content: center; margin-bottom: 8px;">
          <div class="logo-badge">IR</div>
          <span>IntelliRec</span>
        </div>
        <p style="text-align: center; color: var(--text-muted); font-size: 13.5px; margin-bottom: 18px;">
          Content Intelligence & Recommendation Platform
        </p>

        <div class="auth-tabs">
          <button class="auth-tab active" id="tabLogin" onclick="switchAuthTab('login')">Sign In</button>
          <button class="auth-tab" id="tabRegister" onclick="switchAuthTab('register')">Create Account</button>
        </div>

        <div id="authFormArea"></div>

        <div class="demo-logins-box">
          <small>⚡ Quick 1-Click Demo Personas</small>
          <div class="demo-btn-group">
            <button class="btn sm ghost" onclick="quickLogin('admin@intellirec.local', 'Admin@2026!')">
              🛡️ Admin Access
            </button>
            <button class="btn sm ghost" onclick="quickLogin('sarah.data@intellirec.local', 'User@2026!')">
              📊 Sarah (AI/Data)
            </button>
          </div>
          <button class="btn sm ghost full" style="margin-top: 6px;" onclick="quickLogin('alex.dev@intellirec.local', 'User@2026!')">
            ☁️ Alex (Cloud & Web Dev)
          </button>
        </div>

        <div style="text-align: center; margin-top: 20px;">
          <a href="/" style="font-size: 13px; color: var(--primary); font-weight: 600;">← Back to Landing Page</a>
        </div>
      </div>
    </div>
  `;
  switchAuthTab('login');
}

function switchAuthTab(type) {
  const formArea = $('authFormArea');
  const tabLogin = $('tabLogin');
  const tabRegister = $('tabRegister');
  if (!formArea) return;

  if (type === 'login') {
    if (tabLogin) tabLogin.classList.add('active');
    if (tabRegister) tabRegister.classList.remove('active');

    formArea.innerHTML = `
      <form onsubmit="event.preventDefault(); handleLogin();">
        <div class="form-group">
          <label>Email Address</label>
          <input id="loginEmail" type="email" placeholder="you@example.com" required>
        </div>
        <div class="form-group">
          <label>Password</label>
          <div class="password-input-wrap">
            <input id="loginPassword" type="password" placeholder="••••••••" required>
            <button type="button" class="toggle-pw-btn" onclick="togglePasswordVisibility('loginPassword')">Show</button>
          </div>
        </div>
        <button type="submit" class="btn full" style="margin-top: 20px;">Sign In to Platform</button>
      </form>
    `;
  } else {
    if (tabLogin) tabLogin.classList.remove('active');
    if (tabRegister) tabRegister.classList.add('active');

    formArea.innerHTML = `
      <form onsubmit="event.preventDefault(); handleRegister();">
        <div class="form-group">
          <label>Full Name</label>
          <input id="regName" placeholder="Dr. Jane Doe" required>
        </div>
        <div class="form-group">
          <label>Email Address</label>
          <input id="regEmail" type="email" placeholder="you@example.com" required>
        </div>
        <div class="form-group">
          <label>Password</label>
          <div class="password-input-wrap">
            <input id="regPassword" type="password" placeholder="Min 8 chars, 1 uppercase, 1 special" oninput="checkPwStrength(this.value)" required>
            <button type="button" class="toggle-pw-btn" onclick="togglePasswordVisibility('regPassword')">Show</button>
          </div>
          <div class="pw-strength-bar">
            <div class="pw-strength-fill" id="pwStrengthFill"></div>
          </div>
          <div id="pwStrengthText" style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Strength: Required</div>
        </div>
        <div class="form-group">
          <label>Initial Interests (Comma Separated)</label>
          <input id="regInterests" placeholder="AI, Machine Learning, Cloud">
        </div>
        <button type="submit" class="btn full" style="margin-top: 14px;">Create Secure Account</button>
      </form>
    `;
  }
}

function togglePasswordVisibility(id) {
  const el = $(id);
  if (!el) return;
  el.type = el.type === 'password' ? 'text' : 'password';
}

function checkPwStrength(p) {
  const fill = $('pwStrengthFill');
  const text = $('pwStrengthText');
  if (!fill || !text) return;

  let score = 0;
  if (p.length >= 8) score++;
  if (/[A-Z]/.test(p)) score++;
  if (/[a-z]/.test(p)) score++;
  if (/\d/.test(p)) score++;
  if (/[^A-Za-z\d]/.test(p)) score++;

  const configs = [
    { width: '20%', color: '#f43f5e', label: 'Weak' },
    { width: '40%', color: '#f43f5e', label: 'Fair' },
    { width: '60%', color: '#f59e0b', label: 'Medium' },
    { width: '80%', color: '#10b981', label: 'Strong' },
    { width: '100%', color: '#059669', label: 'Excellent' },
  ];

  const cfg = configs[Math.max(0, score - 1)] || { width: '0%', color: 'transparent', label: 'Required' };
  fill.style.width = cfg.width;
  fill.style.backgroundColor = cfg.color;
  text.textContent = `Strength: ${cfg.label}`;
}

async function handleLogin() {
  const email = $('loginEmail').value.trim();
  const password = $('loginPassword').value;
  await doLogin(email, password);
}

async function quickLogin(email, password) {
  await doLogin(email, password);
}

async function doLogin(username, password) {
  try {
    const formData = new URLSearchParams({ username, password });
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');

    token = data.access_token;
    localStorage.setItem('ir_token', token);
    location.href = '/app';
  } catch (err) {
    toast(err.message, true);
  }
}

async function handleRegister() {
  const name = $('regName').value.trim();
  const email = $('regEmail').value.trim();
  const password = $('regPassword').value;
  const rawInterests = $('regInterests').value;
  const interests = rawInterests.split(',').map((x) => x.trim()).filter(Boolean);

  try {
    const data = await api('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, interests }),
    });

    token = data.access_token;
    localStorage.setItem('ir_token', token);
    toast('Account created! Loading your intelligence workspace...');
    setTimeout(() => {
      location.href = '/app';
    }, 500);
  } catch (err) {
    toast(err.message, true);
  }
}

function logout() {
  localStorage.removeItem('ir_token');
  location.href = '/';
}

// Start app on dashboard route
if (location.pathname === '/app') {
  initApp();
}
