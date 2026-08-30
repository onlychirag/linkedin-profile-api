"""Comparison page HTML — AWS (full scraper) vs Vercel (limited)."""


def compare_page_html() -> str:
    return r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ontross — Backend Comparison</title>
  <meta name="description" content="Compare AWS (full) vs Vercel (public-only) LinkedIn scraper backends side-by-side.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{
      --bg:#090d1a;--surface:#10152a;--glass:rgba(255,255,255,.04);
      --border:rgba(255,255,255,.08);--border-hover:rgba(255,255,255,.15);
      --ink:#e8ecf4;--muted:#8896b0;--dim:#5a6a85;
      --accent:#3b82f6;--accent2:#8b5cf6;
      --ok:#22c55e;--danger:#ef4444;--warn:#f59e0b;
      --grad:linear-gradient(135deg,#3b82f6,#8b5cf6);
      --glow:0 0 30px rgba(59,130,246,.15);
      --radius:14px;
    }
    html{scroll-behavior:smooth}
    body{
      font-family:'Inter',system-ui,sans-serif;
      background:var(--bg);color:var(--ink);
      min-height:100vh;
      background-image:radial-gradient(ellipse 80% 50% at 50% -20%,rgba(59,130,246,.12),transparent);
    }

    /* ── Topbar ── */
    .topbar{
      position:sticky;top:0;z-index:10;
      border-bottom:1px solid var(--border);
      background:rgba(9,13,26,.85);backdrop-filter:blur(20px);
    }
    .topbar-inner{
      max-width:1100px;margin:0 auto;padding:0 24px;
      min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:16px;
    }
    .brand{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:800;letter-spacing:-.01em;text-decoration:none;color:var(--ink)}
    .brand-mark{
      width:34px;height:34px;border-radius:8px;display:grid;place-items:center;
      background:var(--grad);color:#fff;font-weight:900;font-size:14px;
    }
    nav{display:flex;gap:6px;flex-wrap:wrap}
    nav a{
      padding:7px 14px;border-radius:8px;font-size:13px;font-weight:700;
      color:var(--muted);text-decoration:none;
      border:1px solid transparent;transition:all .2s;
    }
    nav a:hover,nav a.active{color:var(--ink);background:var(--glass);border-color:var(--border)}

    /* ── Container ── */
    .container{max-width:1100px;margin:0 auto;padding:0 24px}

    /* ── Hero ── */
    .hero{padding:56px 0 32px;text-align:center}
    .hero h1{
      font-size:42px;font-weight:900;line-height:1.1;letter-spacing:-.03em;
      background:linear-gradient(135deg,#fff 40%,#8b9dc3);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    }
    .hero-sub{color:var(--muted);font-size:16px;line-height:1.6;margin-top:12px;max-width:600px;margin-left:auto;margin-right:auto}

    /* ── Toggle ── */
    .toggle-bar{
      display:flex;justify-content:center;gap:0;margin:32px auto 28px;
      background:var(--surface);border:1px solid var(--border);border-radius:12px;
      padding:4px;max-width:480px;
    }
    .toggle-btn{
      flex:1;padding:12px 20px;border:none;border-radius:9px;
      font-family:inherit;font-size:14px;font-weight:700;
      cursor:pointer;transition:all .25s;
      background:transparent;color:var(--muted);
      display:flex;align-items:center;justify-content:center;gap:8px;
    }
    .toggle-btn.active{
      background:var(--grad);color:#fff;
      box-shadow:0 4px 16px rgba(59,130,246,.3);
    }
    .toggle-btn:not(.active):hover{color:var(--ink);background:var(--glass)}
    .toggle-icon{font-size:16px}

    /* ── Info Banner ── */
    .info-banner{
      max-width:720px;margin:0 auto 28px;padding:16px 20px;
      border-radius:var(--radius);border:1px solid var(--border);
      background:var(--surface);
      display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:start;
      transition:all .3s;
    }
    .info-banner .icon{font-size:22px;margin-top:2px}
    .info-banner h3{font-size:14px;font-weight:800;margin-bottom:4px}
    .info-banner p{color:var(--muted);font-size:13px;line-height:1.55}
    .info-banner.aws{border-color:rgba(34,197,94,.2)}
    .info-banner.vercel{border-color:rgba(245,158,11,.2)}

    /* ── Feature Comparison ── */
    .comparison{
      display:grid;grid-template-columns:1fr 1fr;gap:16px;
      max-width:720px;margin:0 auto 32px;
    }
    .feature-card{
      background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:18px;transition:all .3s;
    }
    .feature-card:hover{border-color:var(--border-hover);transform:translateY(-1px)}
    .feature-card .label{
      font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;
      color:var(--dim);margin-bottom:8px;
    }
    .feature-card .value{font-size:15px;font-weight:700;display:flex;align-items:center;gap:6px}
    .check{color:var(--ok)}
    .cross{color:var(--danger)}
    .partial{color:var(--warn)}

    /* ── Limitations ── */
    .limits{
      max-width:720px;margin:0 auto 32px;
      background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:20px;
    }
    .limits h3{font-size:15px;font-weight:800;margin-bottom:12px;display:flex;align-items:center;gap:8px}
    .limits ul{list-style:none;display:grid;gap:8px}
    .limits li{
      padding:10px 14px;border-radius:8px;background:var(--glass);border:1px solid var(--border);
      font-size:13px;color:var(--muted);line-height:1.5;
      display:flex;align-items:flex-start;gap:10px;
    }
    .limits li .icon{flex-shrink:0;margin-top:1px}

    /* ── Workspace ── */
    .workspace{
      display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:18px;
      align-items:start;padding-bottom:60px;max-width:1100px;margin:0 auto;
    }
    .panel{
      background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:22px;
    }
    .panel h2{font-size:18px;font-weight:800;margin-bottom:16px;letter-spacing:-.01em}
    .panel-badge{
      display:inline-flex;align-items:center;gap:6px;padding:4px 10px;
      border-radius:999px;font-size:11px;font-weight:700;margin-left:8px;
      vertical-align:middle;
    }
    .panel-badge.aws-badge{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.2)}
    .panel-badge.vercel-badge{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.2)}
    label{display:block;margin-bottom:8px;color:var(--dim);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
    input[type="url"]{
      width:100%;padding:12px 14px;border-radius:8px;font-size:14px;
      border:1px solid var(--border);background:var(--glass);color:var(--ink);
      font-family:inherit;transition:all .2s;
    }
    input[type="url"]:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(59,130,246,.15)}
    .submit-btn{
      width:100%;padding:14px;margin-top:14px;border:0;border-radius:8px;
      background:var(--grad);color:#fff;font-family:inherit;font-size:14px;font-weight:800;
      cursor:pointer;transition:all .25s;position:relative;overflow:hidden;
    }
    .submit-btn:hover{box-shadow:0 6px 24px rgba(59,130,246,.3);transform:translateY(-1px)}
    .submit-btn:disabled{opacity:.6;cursor:progress;transform:none}
    .submit-btn .spinner{
      display:none;width:18px;height:18px;border:2px solid rgba(255,255,255,.3);
      border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;
      margin:0 auto;
    }
    .submit-btn.loading .label{visibility:hidden}
    .submit-btn.loading .spinner{display:block;position:absolute;top:50%;left:50%;margin:-9px 0 0 -9px}
    @keyframes spin{to{transform:rotate(360deg)}}
    .status-msg{margin-top:14px;font-size:13px;color:var(--muted);min-height:20px;overflow-wrap:anywhere}
    .status-msg.ok{color:var(--ok)}
    .status-msg.error{color:var(--danger)}

    .summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}
    .summary-item{
      padding:12px;border-radius:8px;background:var(--glass);border:1px solid var(--border);
    }
    .summary-item span{display:block;color:var(--dim);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
    .summary-item strong{display:block;margin-top:5px;font-size:16px;overflow-wrap:anywhere}

    pre{
      margin:0;min-height:480px;max-height:calc(100vh - 200px);overflow:auto;
      padding:18px;border-radius:8px;
      background:rgba(0,0,0,.4);border:1px solid var(--border);
      font:13px/1.6 'SF Mono',Consolas,'Liberation Mono',monospace;
      color:#93c5fd;white-space:pre-wrap;word-break:break-word;
    }
    pre .json-key{color:#60a5fa}
    pre .json-str{color:#a78bfa}
    pre .json-num{color:#34d399}
    pre .json-bool{color:#fb923c}
    pre .json-null{color:#6b7280}

    footer{
      border-top:1px solid var(--border);padding:28px 0;
      text-align:center;color:var(--dim);font-size:13px;
    }
    footer a{color:var(--muted);text-decoration:none;font-weight:600}
    footer a:hover{color:var(--ink)}

    .fade-up{opacity:0;transform:translateY(20px);transition:opacity .6s ease,transform .6s ease}
    .fade-up.visible{opacity:1;transform:translateY(0)}

    @media(max-width:860px){
      .hero h1{font-size:30px}
      .comparison{grid-template-columns:1fr}
      .workspace{grid-template-columns:1fr}
      .topbar-inner{flex-direction:column;align-items:flex-start;padding:14px 24px;gap:10px}
      pre{min-height:320px;max-height:none}
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a href="/" class="brand"><span class="brand-mark">in</span><span>Ontross</span></a>
      <nav>
        <a href="/">Home</a>
        <a href="/compare" class="active">Compare</a>
        <a href="/docs">Docs</a>
        <a href="/health">Health</a>
      </nav>
    </div>
  </div>

  <main class="container">
    <section class="hero fade-up">
      <h1>AWS vs Vercel Backend</h1>
      <p class="hero-sub">Compare two deployment modes for the LinkedIn Profile API. AWS uses an authenticated browser for full data. Vercel uses public-only scraping.</p>
    </section>

    <!-- Toggle -->
    <div class="toggle-bar fade-up" id="mode-toggle">
      <button class="toggle-btn active" data-mode="aws" type="button">
        <span class="toggle-icon">☁️</span> AWS Server
      </button>
      <button class="toggle-btn" data-mode="vercel" type="button">
        <span class="toggle-icon">▲</span> Vercel
      </button>
    </div>

    <!-- AWS Info -->
    <div class="info-banner aws fade-up" id="info-aws">
      <span class="icon">🟢</span>
      <div>
        <h3>AWS Server — Full Power Mode</h3>
        <p>Uses a headless Chromium browser on AWS (54.152.33.214) with an authenticated LinkedIn session. Extracts the richest data including detailed experience with dates, education fields, skills, certifications, and languages.</p>
      </div>
    </div>
    <div class="info-banner vercel fade-up" id="info-vercel" style="display:none">
      <span class="icon">🟡</span>
      <div>
        <h3>Vercel — Serverless Public Mode</h3>
        <p>Deployed on Vercel's serverless edge network at <strong>ontross.vercel.app</strong>. Uses public HTTP scraping without an authenticated browser session. Fast and free, but returns limited data compared to the full AWS scraper.</p>
      </div>
    </div>

    <!-- Feature Comparison Grid -->
    <div class="comparison fade-up" id="features">
      <!-- Filled by JS -->
    </div>

    <!-- Limitations -->
    <div class="limits fade-up" id="limits-box">
      <!-- Filled by JS -->
    </div>

    <!-- Workspace -->
    <section class="workspace fade-up" id="workspace">
      <div class="panel">
        <h2>Profile Lookup <span class="panel-badge aws-badge" id="mode-badge">☁️ AWS</span></h2>
        <form id="scrape-form">
          <label for="profile-url">Profile URL</label>
          <input id="profile-url" name="profile-url" type="url"
            value="https://www.linkedin.com/in/chirag-kakwani-8b4055284/" autocomplete="url" required>
          <button id="submit-button" class="submit-btn" type="submit">
            <span class="label">Scrape Profile</span>
            <span class="spinner"></span>
          </button>
          <div id="status" class="status-msg"></div>
        </form>
        <div class="summary" id="summary-grid">
          <div class="summary-item"><span>Name</span><strong id="s-name">—</strong></div>
          <div class="summary-item"><span>Location</span><strong id="s-location">—</strong></div>
          <div class="summary-item"><span>Experience</span><strong id="s-experience">—</strong></div>
          <div class="summary-item"><span>Education</span><strong id="s-education">—</strong></div>
          <div class="summary-item"><span>Skills</span><strong id="s-skills">—</strong></div>
          <div class="summary-item"><span>Certifications</span><strong id="s-certs">—</strong></div>
          <div class="summary-item"><span>Languages</span><strong id="s-langs">—</strong></div>
          <div class="summary-item"><span>Photos</span><strong id="s-photos">—</strong></div>
        </div>
      </div>
      <div class="panel">
        <h2>Response Body</h2>
        <pre id="output">{}</pre>
      </div>
    </section>
  </main>

  <footer>
    <div class="container">
      Built for the Tross hiring challenge &middot;
      <a href="https://github.com/onlychirag/linkedin-profile-api" target="_blank" rel="noopener noreferrer">GitHub</a>
    </div>
  </footer>

  <script>
    const AWS_BASE = 'http://54.152.33.214:8000';
    const VERCEL_BASE = 'https://ontross.vercel.app';

    const MODES = {
      aws: {
        base: AWS_BASE,
        badge: '☁️ AWS',
        badgeClass: 'aws-badge',
        features: [
          { label: 'Profile Name & Headline', status: 'check', text: 'Full' },
          { label: 'Experience (detailed)', status: 'check', text: 'Titles, companies, dates, duration' },
          { label: 'Education (detailed)', status: 'check', text: 'School, degree, field, dates' },
          { label: 'Skills', status: 'check', text: 'Full list' },
          { label: 'Certifications', status: 'check', text: 'Name, issuer, dates' },
          { label: 'Languages', status: 'check', text: 'Full list' },
          { label: 'Profile Photo', status: 'check', text: 'HD via proxy' },
          { label: 'About / Summary', status: 'check', text: 'Full text' },
        ],
        limits: [
          { icon: '⚡', text: 'Runs on AWS datacenter IP — LinkedIn may flag the session after repeated use, requiring a cookie refresh.' },
          { icon: '🔄', text: 'Session cookie must be periodically refreshed via the stealth_login.py script.' },
          { icon: '💰', text: 'Requires a running EC2 instance (~$8/month for t3.micro).' },
        ],
        limitsTitle: '⚠️ AWS Limitations',
      },
      vercel: {
        base: VERCEL_BASE,
        badge: '▲ Vercel',
        badgeClass: 'vercel-badge',
        features: [
          { label: 'Profile Name & Headline', status: 'check', text: 'Full' },
          { label: 'Experience (detailed)', status: 'partial', text: 'Basic — raw text only' },
          { label: 'Education (detailed)', status: 'partial', text: 'Basic — raw text only' },
          { label: 'Skills', status: 'cross', text: 'Not available (requires auth)' },
          { label: 'Certifications', status: 'cross', text: 'Not available (requires auth)' },
          { label: 'Languages', status: 'cross', text: 'Not available (requires auth)' },
          { label: 'Profile Photo', status: 'partial', text: 'May be blocked by LinkedIn' },
          { label: 'About / Summary', status: 'check', text: 'Available if profile is public' },
        ],
        limits: [
          { icon: '🔒', text: 'No authenticated session — LinkedIn returns only public-facing data.' },
          { icon: '📉', text: 'Skills, certifications, and languages are NOT returned because LinkedIn hides them behind login.' },
          { icon: '📝', text: 'Experience and education come as raw text strings instead of structured objects with dates.' },
          { icon: '⏱️', text: 'Vercel serverless functions have a 10-second timeout on the free tier — complex profiles may fail.' },
          { icon: '🌐', text: 'Vercel uses datacenter IPs which LinkedIn may throttle with HTTP 999 responses.' },
        ],
        limitsTitle: '⚠️ Vercel Limitations',
      }
    };

    let currentMode = 'aws';

    const statusIcons = { check: '✅', cross: '❌', partial: '⚠️' };

    function renderFeatures(mode) {
      const grid = document.getElementById('features');
      grid.innerHTML = MODES[mode].features.map(f => `
        <div class="feature-card">
          <div class="label">${f.label}</div>
          <div class="value"><span class="${f.status}">${statusIcons[f.status]}</span> ${f.text}</div>
        </div>
      `).join('');
    }

    function renderLimits(mode) {
      const box = document.getElementById('limits-box');
      const m = MODES[mode];
      box.innerHTML = `
        <h3>${m.limitsTitle}</h3>
        <ul>${m.limits.map(l => `<li><span class="icon">${l.icon}</span>${l.text}</li>`).join('')}</ul>
      `;
    }

    function switchMode(mode) {
      currentMode = mode;
      document.querySelectorAll('.toggle-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
      });
      document.getElementById('info-aws').style.display = mode === 'aws' ? '' : 'none';
      document.getElementById('info-vercel').style.display = mode === 'vercel' ? '' : 'none';
      const badge = document.getElementById('mode-badge');
      badge.textContent = MODES[mode].badge;
      badge.className = 'panel-badge ' + MODES[mode].badgeClass;
      renderFeatures(mode);
      renderLimits(mode);
    }

    document.querySelectorAll('.toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => switchMode(btn.dataset.mode));
    });

    // Init
    switchMode('aws');

    // Fade-in
    const observer = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target) } })
    }, { threshold: .15 });
    document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

    // JSON highlight
    function highlightJSON(json) {
      var h = json.replace(/&/g, '&amp;').replace(/</g, '&lt;');
      return h.replace(/"([^"]*)"\s*:/g, (m, k) => '<span class="json-key">"' + k + '"</span>:')
              .replace(/:\s*"([^"]*)"/g, (m, v) => ': <span class="json-str">"' + v + '"</span>')
              .replace(/:\s*(true|false)/g, (m, v) => ': <span class="json-bool">' + v + '</span>')
              .replace(/:\s*null/g, ': <span class="json-null">null</span>')
              .replace(/:\s*(-?[0-9.]+)/g, (m, v) => ': <span class="json-num">' + v + '</span>');
    }

    // Scrape form
    const form = document.getElementById('scrape-form');
    const input = document.getElementById('profile-url');
    const output = document.getElementById('output');
    const statusEl = document.getElementById('status');
    const button = document.getElementById('submit-button');

    function setSummary(p) {
      document.getElementById('s-name').textContent = p?.name || '—';
      document.getElementById('s-location').textContent = p?.location || '—';
      document.getElementById('s-experience').textContent = Array.isArray(p?.experience) ? String(p.experience.length) : '—';
      document.getElementById('s-education').textContent = Array.isArray(p?.education) ? String(p.education.length) : '—';
      document.getElementById('s-skills').textContent = Array.isArray(p?.skills) ? String(p.skills.length) : '—';
      document.getElementById('s-certs').textContent = Array.isArray(p?.certifications) ? String(p.certifications.length) : '—';
      document.getElementById('s-langs').textContent = Array.isArray(p?.languages) ? String(p.languages.length) : '—';
      document.getElementById('s-photos').textContent = Array.isArray(p?.profile_images) ? String(p.profile_images.length) : '—';
    }

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const base = MODES[currentMode].base;
      const apiUrl = base + '/api/profile?url=' + encodeURIComponent(input.value);
      statusEl.className = 'status-msg'; statusEl.textContent = 'Running scrape via ' + (currentMode === 'aws' ? 'AWS' : 'Vercel') + '…';
      button.disabled = true; button.classList.add('loading');
      output.textContent = '{}'; setSummary(null);
      try {
        const r = await fetch(apiUrl);
        const t = await r.text(); let p;
        try { p = JSON.parse(t); output.innerHTML = highlightJSON(JSON.stringify(p, null, 2)); if (r.ok) setSummary(p) }
        catch { output.textContent = t || '{}' }
        if (!r.ok) throw new Error(p?.detail || 'Request failed with ' + r.status);
        statusEl.className = 'status-msg ok'; statusEl.textContent = 'Done (' + currentMode.toUpperCase() + ')';
      } catch (err) { statusEl.className = 'status-msg error'; statusEl.textContent = err.message }
      finally { button.disabled = false; button.classList.remove('loading') }
    });
  </script>
</body>
</html>
"""
