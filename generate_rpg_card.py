"""
generate_rpg_card.py
─────────────────────
Fetches REAL GitHub stats via API, calculates RPG stat values
dynamically, then renders and commits rpg-card.svg.

Stats mapping:
  STR (Problem Solving)  → total commits + issues closed
  INT (System Design)    → repo count + unique topics used
  DEX (Frontend Craft)   → JS/TS/CSS/HTML byte share %
  WIS (Backend Logic)    → Python/Go/Java/Rust byte share %
  CON (DevOps / Infra)   → Docker/Shell/YAML file presence
  CHA (Open Source)      → stars received + forks + PRs merged
"""

import os
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ─── Config ──────────────────────────────────────────────────────────────────
USERNAME  = "GauravS13"
SVG_PATH  = "rpg-card.svg"
MAX_STAT  = 100      # cap for each stat
# ─────────────────────────────────────────────────────────────────────────────


def gh_get(path: str, token: str) -> dict | list:
    """GET from GitHub REST API."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "User-Agent":    "rpg-card-generator",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def gh_graphql(query: str, token: str) -> dict:
    """POST to GitHub GraphQL API."""
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "User-Agent":    "rpg-card-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def clamp(val: float, lo=0, hi=MAX_STAT) -> int:
    return int(max(lo, min(hi, val)))





def fetch_all_stats(token: str) -> dict:
    print("📡 Fetching GitHub stats...")

    # ── User profile ──────────────────────────────────────────────────────────
    user    = gh_get(f"/users/{USERNAME}", token)
    pub_repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)

    # ── All public repos ──────────────────────────────────────────────────────
    repos = []
    page  = 1
    while True:
        batch = gh_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=owner", token)
        if not batch:
            break
        repos.extend(batch)
        page += 1

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0)       for r in repos)

    # ── Language bytes across all repos ──────────────────────────────────────
    lang_bytes: dict[str, int] = {}
    for repo in repos[:30]:   # limit to avoid rate limit
        name = repo["name"]
        try:
            langs = gh_get(f"/repos/{USERNAME}/{name}/languages", token)
            for lang, size in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + size
        except Exception:
            pass

    total_bytes = sum(lang_bytes.values()) or 1

    frontend_langs  = {"JavaScript", "TypeScript", "HTML", "CSS", "Vue", "Svelte"}
    backend_langs   = {"Python", "Go", "Java", "Rust", "C++", "C", "Ruby", "PHP", "Kotlin"}
    devops_langs    = {"Shell", "Dockerfile", "HCL", "YAML"}

    frontend_pct = sum(lang_bytes.get(l, 0) for l in frontend_langs) / total_bytes * 100
    backend_pct  = sum(lang_bytes.get(l, 0) for l in backend_langs)  / total_bytes * 100
    devops_pct   = sum(lang_bytes.get(l, 0) for l in devops_langs)   / total_bytes * 100

    # ── Contribution stats via GraphQL ────────────────────────────────────────
    gql = """
    {
      user(login: "%s") {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
        }
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT]) {
          totalCount
        }
      }
    }
    """ % USERNAME

    gql_data   = gh_graphql(gql, token)
    contrib    = gql_data["data"]["user"]["contributionsCollection"]
    commits    = contrib.get("totalCommitContributions", 0)
    prs        = contrib.get("totalPullRequestContributions", 0)
    issues     = contrib.get("totalIssueContributions", 0)
    reviews    = contrib.get("totalPullRequestReviewContributions", 0)
    ext_repos  = gql_data["data"]["user"]["repositoriesContributedTo"]["totalCount"]

    # ── Compute RPG stats ─────────────────────────────────────────────────────
    # STR: Problem Solving — commits + issues (log-scaled, ~500 commits = 80)
    str_raw  = math.log1p(commits + issues * 2) / math.log1p(700) * 100
    str_val  = clamp(str_raw)

    # INT: System Design — repos + PRs + reviews
    int_raw  = math.log1p(pub_repos * 3 + prs + reviews) / math.log1p(120) * 100
    int_val  = clamp(int_raw)

    # DEX: Frontend — % of frontend languages, weighted
    dex_val  = clamp(frontend_pct * 1.2)

    # WIS: Backend — % of backend languages
    wis_val  = clamp(backend_pct * 1.3)

    # CON: DevOps — % devops langs + docker/CI file presence (bonus)
    con_val  = clamp(devops_pct * 3 + ext_repos * 0.8)

    # CHA: Open Source — stars, forks, followers (log-scaled)
    cha_raw  = math.log1p(total_stars * 3 + total_forks * 2 + followers) / math.log1p(300) * 100
    cha_val  = clamp(cha_raw)

    # ── Level: sum of all stats / 30 (max level 20) ───────────────────────────
    stat_sum = str_val + int_val + dex_val + wis_val + con_val + cha_val
    level    = clamp(int(stat_sum / 30), 1, 20)

    # ── HP / MP / XP bars ─────────────────────────────────────────────────────
    hp_current = min(commits * 2, 9999)
    mp_current = min(prs * 10 + reviews * 5, 9999)
    xp_current = min(stat_sum * 15, 99999)

    print(f"✅ STR={str_val} INT={int_val} DEX={dex_val} WIS={wis_val} CON={con_val} CHA={cha_val} LVL={level}")

    return {
        "username":    USERNAME,
        "name":        user.get("name") or USERNAME,
        "level":       level,
        "commits":     commits,
        "prs":         prs,
        "issues":      issues,
        "stars":       total_stars,
        "forks":       total_forks,
        "followers":   followers,
        "pub_repos":   pub_repos,
        "hp":          (hp_current, max(hp_current, 1000)),
        "mp":          (mp_current, max(mp_current, 500)),
        "xp":          (xp_current, max(xp_current, 10000)),
        "STR":         str_val,
        "INT":         int_val,
        "DEX":         dex_val,
        "WIS":         wis_val,
        "CON":         con_val,
        "CHA":         cha_val,
        "top_lang":    max(lang_bytes, key=lang_bytes.get) if lang_bytes else "Code",
        "updated":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def bar_width(val: int, track_w: int = 240) -> int:
    return int(val / 100 * track_w)


def hp_bar_width(current: int, maximum: int, track_w: int = 190) -> int:
    return int(current / maximum * track_w)


def render_svg(s: dict) -> str:
    """Render the full RPG card SVG from stats dict."""

    def stat_row(y, abbr, label, val, delay):
        bw    = bar_width(val, 260)
        return f"""
  <text x="385" y="{y}" fill="#888" font-size="9" letter-spacing="1">{abbr}</text>
  <text x="418" y="{y}" fill="#ffffff" font-size="10" font-weight="bold">{label}</text>
  <rect x="530" y="{y-13}" width="260" height="14" rx="3" fill="#1a0535" stroke="#2a0550" stroke-width="0.8"/>
  <rect x="530" y="{y-13}" width="0"   height="14" rx="3" fill="url(#barGrad)">
    <animate attributeName="width" from="0" to="{bw}" dur="1s" begin="{delay}s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1"/>
  </rect>
  <text x="797" y="{y}" fill="#bf5fff" font-size="10" font-weight="bold">{val}</text>
  <text x="820" y="{y}" fill="#555" font-size="9">/100</text>"""

    hp_c, hp_m = s["hp"]
    mp_c, mp_m = s["mp"]
    xp_c, xp_m = s["xp"]
    hp_w = hp_bar_width(hp_c, hp_m)
    mp_w = hp_bar_width(mp_c, mp_m)
    xp_w = hp_bar_width(xp_c, xp_m)

    # format numbers nicely
    def fmt(n): return f"{n:,}"

    return f"""<svg width="860" height="380" viewBox="0 0 860 380" xmlns="http://www.w3.org/2000/svg" font-family="'Courier New', Courier, monospace">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#0d0221"/>
      <stop offset="50%"  stop-color="#130330"/>
      <stop offset="100%" stop-color="#0d0221"/>
    </linearGradient>
    <linearGradient id="barGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#6c00b5"/>
      <stop offset="100%" stop-color="#bf5fff"/>
    </linearGradient>
    <linearGradient id="hpGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#7b0000"/>
      <stop offset="100%" stop-color="#ff4f7b"/>
    </linearGradient>
    <linearGradient id="mpGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#00207b"/>
      <stop offset="100%" stop-color="#4f9fff"/>
    </linearGradient>
    <linearGradient id="xpGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#7b5500"/>
      <stop offset="100%" stop-color="#ffd700"/>
    </linearGradient>
    <filter id="softGlow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Base card -->
  <rect width="860" height="380" rx="12" fill="url(#bgGrad)"/>
  <rect width="860" height="380" rx="12" fill="none" stroke="#bf5fff" stroke-width="1.5" opacity="0.6"/>
  <rect x="6" y="6" width="848" height="368" rx="9" fill="none" stroke="#6c00b5" stroke-width="0.5" opacity="0.4"/>

  <!-- Grid -->
  <g opacity="0.04" stroke="#bf5fff" stroke-width="0.5">
    {"".join(f'<line x1="0" y1="{y}" x2="860" y2="{y}"/>' for y in range(20,380,20))}
    {"".join(f'<line x1="{x}" y1="0" x2="{x}" y2="380"/>' for x in range(20,860,20))}
  </g>

  <!-- Corners -->
  <g fill="#bf5fff" opacity="0.9" filter="url(#softGlow)">
    <rect x="14" y="14" width="14" height="3"/><rect x="14" y="14" width="3" height="14"/>
    <rect x="832" y="14" width="14" height="3"/><rect x="843" y="14" width="3" height="14"/>
    <rect x="14" y="363" width="14" height="3"/><rect x="14" y="352" width="3" height="14"/>
    <rect x="832" y="363" width="14" height="3"/><rect x="843" y="352" width="3" height="14"/>
  </g>

  <!-- Header -->
  <rect x="14" y="14" width="832" height="38" rx="4" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <polygon points="26,33 32,27 38,33 32,39" fill="#bf5fff" opacity="0.8"/>
  <polygon points="822,33 828,27 834,33 828,39" fill="#bf5fff" opacity="0.8"/>
  <text x="430" y="39" text-anchor="middle" fill="#bf5fff" font-size="14" font-weight="bold" letter-spacing="8" filter="url(#softGlow)">✦  CHARACTER  SHEET  ✦</text>
  <line x1="14" y1="58" x2="846" y2="58" stroke="#6c00b5" stroke-width="0.8" opacity="0.6"/>

  <!-- Avatar box -->
  <rect x="24" y="68" width="88" height="88" rx="4" fill="#1a0535" stroke="#bf5fff" stroke-width="1.5"/>
  <rect x="28" y="72" width="80" height="80" rx="2" fill="#0d0221" stroke="#6c00b5" stroke-width="0.5" opacity="0.6"/>
  <rect x="50" y="80" width="28" height="24" rx="3" fill="#bf5fff" opacity="0.9"/>
  <rect x="56" y="87" width="5" height="5" fill="#0d0221"/>
  <rect x="67" y="87" width="5" height="5" fill="#0d0221"/>
  <rect x="57" y="97" width="14" height="2" fill="#0d0221" rx="1"/>
  <rect x="46" y="106" width="36" height="26" rx="2" fill="#6c00b5" opacity="0.9"/>
  <rect x="36" y="108" width="10" height="18" rx="2" fill="#6c00b5" opacity="0.7"/>
  <rect x="82" y="108" width="10" height="18" rx="2" fill="#6c00b5" opacity="0.7"/>
  <text x="64" y="124" text-anchor="middle" font-size="10" fill="#bf5fff" font-weight="bold">&lt;/&gt;</text>

  <!-- Name & class -->
  <text x="126" y="86" fill="#ffffff" font-size="20" font-weight="bold" letter-spacing="2">{s["name"].upper()}</text>
  <text x="126" y="104" fill="#bf5fff" font-size="11" letter-spacing="4">FULL STACK DEVELOPER</text>
  <rect x="126" y="113" width="80" height="20" rx="3" fill="#1a0535" stroke="#bf5fff" stroke-width="1"/>
  <text x="166" y="127" text-anchor="middle" fill="#ffd700" font-size="10" font-weight="bold" letter-spacing="1">⚔  LVL  {s["level"]:02d}</text>
  <rect x="215" y="113" width="135" height="20" rx="3" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <text x="282" y="127" text-anchor="middle" fill="#bf5fff" font-size="10">TOP LANG: {s["top_lang"].upper()}</text>

  <!-- HP -->
  <text x="126" y="152" fill="#ff4f7b" font-size="10" font-weight="bold" letter-spacing="1">HP</text>
  <text x="340" y="152" text-anchor="end" fill="#888" font-size="9">{fmt(hp_c)} / {fmt(hp_m)}</text>
  <rect x="150" y="141" width="190" height="12" rx="3" fill="#1a0535" stroke="#7b0000" stroke-width="0.8"/>
  <rect x="150" y="141" width="0" height="12" rx="3" fill="url(#hpGrad)">
    <animate attributeName="width" from="0" to="{hp_w}" dur="1.2s" begin="0.2s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1"/>
  </rect>

  <!-- MP -->
  <text x="126" y="173" fill="#4f9fff" font-size="10" font-weight="bold" letter-spacing="1">MP</text>
  <text x="340" y="173" text-anchor="end" fill="#888" font-size="9">{fmt(mp_c)} / {fmt(mp_m)}</text>
  <rect x="150" y="162" width="190" height="12" rx="3" fill="#1a0535" stroke="#00207b" stroke-width="0.8"/>
  <rect x="150" y="162" width="0" height="12" rx="3" fill="url(#mpGrad)">
    <animate attributeName="width" from="0" to="{mp_w}" dur="1.2s" begin="0.4s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1"/>
  </rect>

  <!-- XP -->
  <text x="126" y="194" fill="#ffd700" font-size="10" font-weight="bold" letter-spacing="1">XP</text>
  <text x="340" y="194" text-anchor="end" fill="#888" font-size="9">{fmt(xp_c)} / {fmt(xp_m)}</text>
  <rect x="150" y="183" width="190" height="12" rx="3" fill="#1a0535" stroke="#7b5500" stroke-width="0.8"/>
  <rect x="150" y="183" width="0" height="12" rx="3" fill="url(#xpGrad)">
    <animate attributeName="width" from="0" to="{xp_w}" dur="1.2s" begin="0.6s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1"/>
  </rect>

  <!-- Status badges -->
  <rect x="126" y="206" width="68" height="18" rx="9" fill="#1a0535" stroke="#22c55e" stroke-width="1"/>
  <text x="160" y="219" text-anchor="middle" fill="#22c55e" font-size="9" letter-spacing="1">● ACTIVE</text>
  <rect x="202" y="206" width="88" height="18" rx="9" fill="#1a0535" stroke="#ffd700" stroke-width="1"/>
  <text x="246" y="219" text-anchor="middle" fill="#ffd700" font-size="9" letter-spacing="1">⚡ GRINDING</text>
  <rect x="298" y="206" width="44" height="18" rx="9" fill="#1a0535" stroke="#bf5fff" stroke-width="1"/>
  <text x="320" y="219" text-anchor="middle" fill="#bf5fff" font-size="9" letter-spacing="1">🔥 OP</text>

  <!-- Stats summary boxes -->
  <rect x="24" y="238" width="154" height="34" rx="4" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <text x="101" y="252" text-anchor="middle" fill="#888" font-size="8" letter-spacing="2">COMMITS</text>
  <text x="101" y="265" text-anchor="middle" fill="#bf5fff" font-size="12" font-weight="bold">{fmt(s["commits"])}</text>

  <rect x="186" y="238" width="80" height="34" rx="4" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <text x="226" y="252" text-anchor="middle" fill="#888" font-size="8" letter-spacing="2">STARS</text>
  <text x="226" y="265" text-anchor="middle" fill="#ffd700" font-size="12" font-weight="bold">{fmt(s["stars"])}</text>

  <rect x="274" y="238" width="76" height="34" rx="4" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <text x="312" y="252" text-anchor="middle" fill="#888" font-size="8" letter-spacing="2">PRs</text>
  <text x="312" y="265" text-anchor="middle" fill="#22c55e" font-size="12" font-weight="bold">{fmt(s["prs"])}</text>

  <!-- Active quest -->
  <rect x="24" y="282" width="326" height="36" rx="4" fill="#1a0535" stroke="#ffd700" stroke-width="1" opacity="0.9"/>
  <text x="36" y="297" fill="#ffd700" font-size="9" font-weight="bold" letter-spacing="2">ACTIVE QUEST</text>
  <text x="36" y="311" fill="#c9d1d9" font-size="9" opacity="0.85">📜 Master System Design</text>

  <!-- Equipment -->
  <rect x="24" y="326" width="326" height="36" rx="4" fill="#1a0535" stroke="#6c00b5" stroke-width="1"/>
  <text x="36" y="341" fill="#bf5fff" font-size="9" font-weight="bold" letter-spacing="2">EQUIPPED</text>
  <text x="36" y="354" fill="#c9d1d9" font-size="8" opacity="0.85">⌨ Mech KB | ☕ Infinite Coffee | 🎧 Lo-fi | 🖥 Dual Monitor</text>

  <!-- Divider -->
  <line x1="364" y1="62" x2="364" y2="368" stroke="#6c00b5" stroke-width="1" opacity="0.5" stroke-dasharray="4,4"/>
  <polygon points="364,68 370,74 364,80 358,74" fill="#bf5fff" opacity="0.6"/>
  <polygon points="364,300 370,306 364,312 358,306" fill="#bf5fff" opacity="0.6"/>

  <!-- Right panel: BASE STATS -->
  <text x="606" y="85" text-anchor="middle" fill="#bf5fff" font-size="11" font-weight="bold" letter-spacing="5" opacity="0.9">BASE  STATS</text>
  <line x1="382" y1="92" x2="830" y2="92" stroke="#6c00b5" stroke-width="0.6" opacity="0.5"/>

  {stat_row(120, "STR", "Problem Solving",  s["STR"], 0.30)}
  {stat_row(148, "INT", "System Design",    s["INT"], 0.45)}
  {stat_row(176, "DEX", "Frontend Craft",   s["DEX"], 0.60)}
  {stat_row(204, "WIS", "Backend Logic",    s["WIS"], 0.75)}
  {stat_row(232, "CON", "DevOps / Infra",   s["CON"], 0.90)}
  {stat_row(260, "CHA", "Open Source",      s["CHA"], 1.05)}

  <line x1="382" y1="274" x2="830" y2="274" stroke="#6c00b5" stroke-width="0.6" opacity="0.5"/>

  <!-- Traits -->
  <text x="606" y="291" text-anchor="middle" fill="#bf5fff" font-size="9" font-weight="bold" letter-spacing="5" opacity="0.9">TRAITS</text>
  <rect x="382" y="300" width="82" height="20" rx="10" fill="#1a0535" stroke="#bf5fff" stroke-width="0.8"/>
  <text x="423" y="314" text-anchor="middle" fill="#bf5fff" font-size="9">⚡ Fast Learner</text>
  <rect x="472" y="300" width="90" height="20" rx="10" fill="#1a0535" stroke="#bf5fff" stroke-width="0.8"/>
  <text x="517" y="314" text-anchor="middle" fill="#bf5fff" font-size="9">🔍 Debugger++</text>
  <rect x="570" y="300" width="84" height="20" rx="10" fill="#1a0535" stroke="#bf5fff" stroke-width="0.8"/>
  <text x="612" y="314" text-anchor="middle" fill="#bf5fff" font-size="9">☕ Caffeinated</text>
  <rect x="662" y="300" width="84" height="20" rx="10" fill="#1a0535" stroke="#bf5fff" stroke-width="0.8"/>
  <text x="704" y="314" text-anchor="middle" fill="#bf5fff" font-size="9">🌙 Night Coder</text>
  <rect x="754" y="300" width="78" height="20" rx="10" fill="#1a0535" stroke="#bf5fff" stroke-width="0.8"/>
  <text x="793" y="314" text-anchor="middle" fill="#bf5fff" font-size="9">📦 Shipper</text>

  <!-- Footer -->
  <line x1="382" y1="330" x2="830" y2="330" stroke="#6c00b5" stroke-width="0.6" opacity="0.5"/>
  <text x="606" y="347" text-anchor="middle" fill="#555" font-size="9" letter-spacing="2">LAST SYNCED: {s["updated"]}  •  SERVER: GITHUB API</text>
  <text x="606" y="362" text-anchor="middle" fill="#4a1570" font-size="8" letter-spacing="1">⚠ WARNING: THIS CHARACTER KEEPS LEVELING UP</text>
</svg>"""


def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise EnvironmentError("GH_TOKEN is not set.")

    stats = fetch_all_stats(token)
    svg   = render_svg(stats)

    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"🎮 RPG card written to {SVG_PATH}")


if __name__ == "__main__":
    main()
