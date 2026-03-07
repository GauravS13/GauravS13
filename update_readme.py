"""
update_readme.py
────────────────
Fetches pinned repositories from GitHub GraphQL API and
auto-updates the projects section in README.md.

Runs via GitHub Actions — no manual editing needed.
"""

import os
import re
import json
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_USERNAME = "GauravS13"
README_PATH     = "README.md"
START_MARKER    = "<!-- PROJECTS_START -->"
END_MARKER      = "<!-- PROJECTS_END -->"

# ── Language → emoji map (extend as needed) ───────────────────────────────────
LANG_EMOJI = {
    "JavaScript" : "🟨",
    "TypeScript" : "🟦",
    "Python"     : "🐍",
    "Java"       : "☕",
    "Go"         : "🐹",
    "Rust"       : "🦀",
    "C++"        : "⚙️",
    "C"          : "🔧",
    "HTML"       : "🌐",
    "CSS"        : "🎨",
    "Shell"      : "💻",
    "Dockerfile" : "🐳",
}

# ── GitHub GraphQL query ───────────────────────────────────────────────────────
QUERY = """
{
  user(login: "%s") {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name
          description
          url
          homepageUrl
          stargazerCount
          forkCount
          primaryLanguage {
            name
            color
          }
          repositoryTopics(first: 5) {
            nodes {
              topic {
                name
              }
            }
          }
        }
      }
    }
  }
}
""" % GITHUB_USERNAME


def fetch_pinned_repos(token: str) -> list[dict]:
    """Call GitHub GraphQL API and return list of pinned repo dicts."""
    payload = json.dumps({"query": QUERY}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data    = payload,
        headers = {
            "Authorization" : f"Bearer {token}",
            "Content-Type"  : "application/json",
            "User-Agent"    : "readme-updater",
        },
        method  = "POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["data"]["user"]["pinnedItems"]["nodes"]


def repo_to_row(repo: dict) -> str:
    """Convert a repo dict into a markdown table row."""
    name        = repo.get("name", "Untitled")
    description = repo.get("description") or "No description provided."
    repo_url    = repo.get("url", "#")
    live_url    = repo.get("homepageUrl") or ""
    stars       = repo.get("stargazerCount", 0)
    forks       = repo.get("forkCount", 0)

    # Primary language
    lang_info   = repo.get("primaryLanguage") or {}
    lang_name   = lang_info.get("name", "")
    lang_emoji  = LANG_EMOJI.get(lang_name, "📦")

    # Topics → rendered as inline code tags
    topics      = repo.get("repositoryTopics", {}).get("nodes", [])
    topic_tags  = " ".join(
        f"`{t['topic']['name']}`" for t in topics[:4]
    ) if topics else f"`{lang_name}`" if lang_name else ""

    # Demo button — only show if homepageUrl exists
    demo_badge = (
        f'<a href="{live_url}"><img src="https://img.shields.io/badge/LIVE-bf5fff?style=flat-square&logo=vercel&logoColor=white"/></a> '
        if live_url else ""
    )

    code_badge = f'<a href="{repo_url}"><img src="https://img.shields.io/badge/CODE-0d0221?style=flat-square&logo=github&logoColor=white"/></a>'

    stars_forks = f"⭐ {stars} &nbsp; 🍴 {forks}"

    return (
        f"<tr>\n"
        f'<td><b>{lang_emoji} {name}</b><br/><sub>{stars_forks}</sub></td>\n'
        f"<td>{description}</td>\n"
        f"<td>{topic_tags}</td>\n"
        f'<td align="center">{demo_badge}{code_badge}</td>\n'
        f"</tr>\n"
    )


def build_projects_section(repos: list[dict]) -> str:
    """Build the full HTML table block for the projects section."""
    if not repos:
        return "<p align='center'>No pinned repositories found.</p>"

    rows = "\n".join(repo_to_row(r) for r in repos)

    return f"""<!-- PROJECTS_START -->
> 📌 &nbsp; *Auto-synced from my pinned repositories — updated daily*

<table align="center" width="100%">
<thead>
<tr>
<th align="left">🔮 Project</th>
<th align="left">📝 Description</th>
<th align="left">🧱 Stack / Topics</th>
<th align="center">🔗 Links</th>
</tr>
</thead>
<tbody>

{rows}
</tbody>
</table>

<div align="center">
<br/>
<a href="https://github.com/{GITHUB_USERNAME}?tab=repositories">
  <img src="https://img.shields.io/badge/VIEW_ALL_PROJECTS-6c00b5?style=for-the-badge&logo=github&logoColor=white" />
</a>
</div>
<!-- PROJECTS_END -->"""


def update_readme(new_section: str) -> bool:
    """Replace the content between markers in README.md."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern  = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if not pattern.search(content):
        print("❌ Markers not found in README.md — make sure both markers exist.")
        return False

    updated = pattern.sub(new_section, content)

    if updated == content:
        print("✅ README already up to date — no changes needed.")
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"✅ README updated with {len(new_section)} characters of new content.")
    return True


def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise EnvironmentError("GH_TOKEN environment variable is not set.")

    print(f"🔍 Fetching pinned repos for @{GITHUB_USERNAME}...")
    repos = fetch_pinned_repos(token)
    print(f"📦 Found {len(repos)} pinned repo(s).")

    section = build_projects_section(repos)
    changed = update_readme(section)

    if changed:
        print("🚀 README.md has been updated successfully.")
    else:
        print("😴 No update needed.")


if __name__ == "__main__":
    main()
