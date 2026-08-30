from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.errors import AuthenticationRequired, InvalidLinkedInUrl, ScraperError
from app.models import LinkedInProfile
from app.scraper.linkedin import LinkedInScraper
from app.scraper.session import has_persistent_user_data_dir, load_storage_state_data


class SessionUpdate(BaseModel):
    storage_state_b64: str = Field(..., description="Base64-encoded Playwright storage state JSON")

class ProfileRequest(BaseModel):
    url: str = Field(..., examples=["https://www.linkedin.com/in/example/"])


@lru_cache(maxsize=1)
def get_scraper() -> LinkedInScraper:
    return LinkedInScraper(get_settings())


def home_page_html() -> str:
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

    

    

    <section class="section fade-up" id="founders" aria-labelledby="founder-title">
      <div class="section-head">
        <div>
          <p class="eyebrow">Founder Radar</p>
          <h2 id="founder-title">The Hit List.</h2>
        </div>
      </div>

      <div class="founder-grid">
        <article class="founder-card">
          <div class="founder-head">
            <div class="avatar teal">MS</div>
            <div>
              <h3>Meet Shah</h3>
              <p class="role">Co-Founder and CTO at Tross (Previously Ayden)</p>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">San Francisco, CA</span>
            <span class="pill">IIT Roorkee</span>
            <span class="pill">Backend &middot; Security &middot; Infra</span>
          </div>
          <button class="expand-btn" type="button" onclick="toggleDetails(this)"><span class="arrow">&#9660;</span> Details</button>
          <div class="founder-details">
            <p class="detail-label">Experience</p>
            <ul class="timeline">
              <li><strong>Tross</strong> — Co-Founder and CTO, Jun 2025 to Present.</li>
              <li><strong>BharatX</strong> — Founding Engineer; acquired by Flipkart.</li>
              <li><strong>Entrepreneur First</strong> — EIR, Jul–Dec 2023.</li>
              <li><strong>Shape</strong> — Founding SWE, Jan–Jun 2023.</li>
              <li><strong>Microsoft</strong> — Security Intern, May–Jul 2022.</li>
              <li><strong>Hevo Data</strong> — SWE Intern, Nov 2021–Apr 2022.</li>
              <li><strong>GSoC / Open Source</strong> — 2020–2021.</li>
            </ul>
            <p class="detail-label">Education</p>
            <ul class="timeline">
              <li><strong>IIT Roorkee</strong> — BTech CS, 2019–2023.</li>
            </ul>
          </div>
          <div class="founder-actions">
            <button class="btn-scrape" type="button" data-profile-url="https://www.linkedin.com/in/meetcshah19/">Scrape Meet</button>
            <a class="btn-outline" href="https://www.linkedin.com/in/meetcshah19/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
          </div>
        </article>

        <article class="founder-card">
          <div class="founder-head">
            <div class="avatar violet">PK</div>
            <div>
              <h3>Padam Kataria</h3>
              <p class="role">Co-Founder at Tross (Previously Ayden)</p>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">San Francisco Bay Area</span>
            <span class="pill">BITS Pilani</span>
            <span class="pill">Product &middot; Fintech &middot; GTM</span>
          </div>
          <button class="expand-btn" type="button" onclick="toggleDetails(this)"><span class="arrow">&#9660;</span> Details</button>
          <div class="founder-details">
            <p class="detail-label">Experience</p>
            <ul class="timeline">
              <li><strong>Tross</strong> — Co-Founder, Dec 2025 to Present.</li>
              <li><strong>Career break</strong> — Feb–Jun 2025.</li>
              <li><strong>BharatX</strong> — Business Head, May 2024–Feb 2025; acquired by Super.money / Flipkart.</li>
              <li><strong>Zenifi</strong> — Healthcare fintech, Apr 2023–May 2024; acquired by BharatX.</li>
              <li><strong>Navi</strong> — Product, personal loans &amp; KYC, Jan 2022–Apr 2023.</li>
              <li><strong>Hallparty</strong> — Founding Member, Sep 2020–Feb 2021.</li>
              <li><strong>Sprinklr</strong> — CX product work, 2021.</li>
            </ul>
            <p class="detail-label">Education</p>
            <ul class="timeline">
              <li><strong>BITS Pilani</strong> — B.E. (Hons.), Electronics, 2018–2022.</li>
              <li><strong>DPS R.K. Puram</strong> — PCM.</li>
            </ul>
          </div>
          <div class="founder-actions">
            <button class="btn-scrape" type="button" data-profile-url="https://www.linkedin.com/in/padamkataria/">Scrape Padam</button>
            <a class="btn-outline" href="https://www.linkedin.com/in/padamkataria/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
          </div>
        </article>
      </div>
    </section>

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
        
      },
      vercel: {
        base: VERCEL_BASE,
        badge: '▲ Vercel',
        badgeClass: 'vercel-badge',
        
      }
    };

    let currentMode = 'aws';

    

    
    
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

    
    /* ── Collapse / expand founder details ── */
    function toggleDetails(btn){
      const details=btn.nextElementSibling;
      details.classList.toggle('open');
      btn.classList.toggle('open');
    }

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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Hosted API that extracts structured data from LinkedIn profile URLs.",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        return home_page_html()

    @app.get("/ui", response_class=HTMLResponse)
    async def ui() -> str:
        return home_page_html()

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "upstream_proxy_enabled": bool(settings.upstream_api_base_url),
            "browser_backend": settings.browser_backend,
            "browser_scraper_enabled": settings.enable_browser_scraper,
            "auth_http_scraper_enabled": settings.enable_auth_http_scraper,
            "drission_scraper_enabled": settings.enable_drission_scraper,
            "linkedin_credentials_configured": bool(
                settings.linkedin_email and settings.linkedin_password
            ),
            "storage_state_configured": bool(
                settings.linkedin_storage_state_b64
                or settings.linkedin_storage_state_path.exists()
                or has_persistent_user_data_dir(settings)
            ),
        }

    @app.get("/api/image")
    async def proxy_linkedin_image(
        url: str = Query(..., description="LinkedIn media image URL"),
        _: None = Depends(require_api_key),
    ) -> Response:
        if settings.upstream_api_base_url:
            return await _proxy_upstream_image(settings, url)

        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "media.licdn.com":
            raise HTTPException(
                status_code=422,
                detail="Only LinkedIn media image URLs are supported",
            )

        cookies = httpx.Cookies()
        storage_state = load_storage_state_data(settings)
        if storage_state:
            for item in storage_state.get("cookies", []):
                domain = item.get("domain", "")
                if "linkedin.com" not in domain:
                    continue
                name = item.get("name")
                value = item.get("value")
                if not name or value is None:
                    continue
                cookies.set(name, value, domain=domain, path=item.get("path", "/"))

        headers = {
            "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "referer": "https://www.linkedin.com/",
            "user-agent": settings.user_agent,
        }
        async with httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            follow_redirects=True,
            timeout=settings.request_timeout_ms / 1000,
        ) as client:
            image_response = await client.get(url)

        content_type = image_response.headers.get("content-type", "")
        if image_response.status_code >= 400 or not content_type.startswith("image/"):
            raise HTTPException(
                status_code=502,
                detail="LinkedIn image could not be fetched",
            )

        return Response(
            content=image_response.content,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=300"},
        )

    @app.post("/api/v1/profiles", response_model=LinkedInProfile)
    async def scrape_profile_post(
        payload: ProfileRequest,
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        if settings.upstream_api_base_url:
            return await _proxy_upstream_profile(
                settings,
                "POST",
                "/api/v1/profiles",
                json={"url": payload.url},
            )
        return await _scrape(payload.url, scraper)

    @app.get("/api/v1/profiles", response_model=LinkedInProfile)
    async def scrape_profile_get(
        url: str = Query(..., description="LinkedIn /in/ or /pub/ profile URL"),
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        if settings.upstream_api_base_url:
            return await _proxy_upstream_profile(
                settings,
                "GET",
                "/api/v1/profiles",
                params={"url": url},
            )
        return await _scrape(url, scraper)

    @app.get("/api/profile", response_model=LinkedInProfile)
    async def scrape_profile_compat_get(
        url: str = Query(..., description="LinkedIn /in/ or /pub/ profile URL"),
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        if settings.upstream_api_base_url:
            return await _proxy_upstream_profile(
                settings,
                "GET",
                "/api/profile",
                params={"url": url},
            )
        return await _scrape(url, scraper)

    @app.post("/api/auth/session")
    async def update_session(
        payload: SessionUpdate,
        _: None = Depends(require_api_key),
    ) -> dict[str, str]:
        """Hot-swap the LinkedIn session cookie at runtime (no redeploy needed)."""
        import base64 as _b64
        import json as _json

        # Validate the payload is valid base64 JSON
        try:
            decoded = _b64.b64decode(payload.storage_state_b64).decode("utf-8")
            state = _json.loads(decoded)
            if "cookies" not in state:
                raise ValueError("Missing 'cookies' key")
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid storage state: {exc}",
            ) from exc

        # Hot-swap in Settings (bypass frozen dataclass)
        object.__setattr__(settings, "linkedin_storage_state_b64", payload.storage_state_b64)

        # Also persist to the state file so it survives restarts
        state_path = settings.linkedin_storage_state_path
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(decoded, encoding="utf-8")

        # Clear the scraper cache so next request uses the new session
        get_scraper.cache_clear()

        cookie_count = len(state.get("cookies", []))
        return {
            "status": "ok",
            "message": f"Session updated with {cookie_count} cookies. Next scrape will use the new session.",
        }

    return app


async def require_api_key(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    provided = x_api_key or request.query_params.get("api_key")
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


def _upstream_url(settings: Settings, path: str) -> str:
    base_url = (settings.upstream_api_base_url or "").rstrip("/")
    return f"{base_url}{path}"


def _upstream_headers(settings: Settings) -> dict[str, str]:
    headers = {"accept": "application/json"}
    if settings.upstream_api_key:
        headers["x-api-key"] = settings.upstream_api_key
    return headers


async def _proxy_upstream_profile(
    settings: Settings,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    json: dict[str, str] | None = None,
) -> LinkedInProfile:
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_ms / 1000,
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method,
                _upstream_url(settings, path),
                params=params,
                json=json,
                headers=_upstream_headers(settings),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream scraper is unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=_upstream_error_detail(response),
        )

    try:
        return LinkedInProfile.model_validate(response.json())
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Upstream scraper returned an invalid profile response",
        ) from exc


async def _proxy_upstream_image(settings: Settings, url: str) -> Response:
    headers = {"accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"}
    if settings.upstream_api_key:
        headers["x-api-key"] = settings.upstream_api_key

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_ms / 1000,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                _upstream_url(settings, "/api/image"),
                params={"url": url},
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream image proxy is unreachable: {exc}",
        ) from exc

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400 or not content_type.startswith("image/"):
        raise HTTPException(
            status_code=response.status_code if response.status_code >= 400 else 502,
            detail=_upstream_error_detail(response),
        )

    return Response(
        content=response.content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


def _upstream_error_detail(response: httpx.Response) -> str | Any:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or "Upstream scraper request failed"
    if isinstance(data, dict) and "detail" in data:
        return data["detail"]
    return data


async def _scrape(url: str, scraper: LinkedInScraper) -> LinkedInProfile:
    try:
        return await scraper.scrape(url)
    except InvalidLinkedInUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AuthenticationRequired as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except ScraperError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


app = create_app()
