"""Refresh profile assets using only the owner's public repository metadata."""

from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

OWNER = "zhengsuanfa"
ROOT = Path(__file__).resolve().parents[1]


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{OWNER}-profile"}
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(f"https://api.github.com/{path}", headers=headers), timeout=30) as response:
        return json.load(response)


def public_owned(repos):
    return [r for r in repos if r.get("private") is False and r.get("visibility", "public") == "public"
            and r.get("owner", {}).get("login", "").lower() == OWNER.lower()]


def render_metrics(repos, date):
    originals = [r for r in repos if not r["fork"] and r["name"].lower() != OWNER.lower()]
    languages = Counter(r["language"] for r in originals if r["language"])
    top = languages.most_common(4)
    stars = sum(r["stargazers_count"] for r in originals)
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="290" viewBox="0 0 1000 290" role="img" aria-labelledby="title desc">
<title id="title">GitHub public repository snapshot</title>
<desc id="desc">{len(repos)} public repositories; {len(originals)} original project repositories; {stars} stars on original projects. Updated {date} UTC.</desc>
<rect x=".5" y=".5" width="999" height="289" rx="14" fill="#0d1626" stroke="#27374f"/>
<g font-family="ui-monospace, SFMono-Regular, Consolas, monospace">
<text x="32" y="36" font-size="12" letter-spacing="2" fill="#67e8f9">PUBLIC REPOSITORY SNAPSHOT</text>
<text x="968" y="36" text-anchor="end" font-size="11" fill="#8398b8">{date} UTC</text>''']
    for x, value, label in [(32, len(repos), "PUBLIC REPOS"), (365, len(originals), "ORIGINAL PROJECTS"), (700, stars, "STARS ON ORIGINALS")]:
        svg.append(f'<text x="{x}" y="105" font-size="46" font-weight="700" fill="#f0f6ff">{value}</text><text x="{x}" y="136" font-size="12" fill="#9db0ce">{label}</text>')
    svg.append('<path d="M32 161H968" stroke="#27374f"/><text x="32" y="191" font-size="11" fill="#8398b8">PRIMARY LANGUAGES / BY ORIGINAL REPOSITORY COUNT</text>')
    colors = ["#67e8f9", "#a5b4fc", "#6ee7b7", "#fcd34d"]
    total = sum(n for _, n in top) or 1
    x = 32
    for i, (language, count) in enumerate(top):
        width = 936 * count / total
        svg.append(f'<rect x="{x:.2f}" y="208" width="{width:.2f}" height="8" fill="{colors[i]}"/>')
        svg.append(f'<circle cx="{38+i*235}" cy="250" r="4" fill="{colors[i]}"/><text x="{50+i*235}" y="255" font-size="13" fill="#cbd5e1">{escape(language)} · {count}</text>')
        x += width
    svg.append('</g></svg>\n')
    return "\n".join(svg)


def render_activity(repos):
    eligible = [r for r in repos if not r["fork"] and not r.get("archived")
                and r["name"].lower() != OWNER.lower() and r.get("pushed_at")]
    recent = sorted(eligible, key=lambda r: r["pushed_at"], reverse=True)[:5]
    lines = ["| 公开项目 | 最近推送（UTC） |", "| :--- | :--- |"]
    for repo in recent:
        # GitHub repository names cannot contain Markdown delimiters such as ] or |.
        lines.append(f'| [{repo["name"]}](https://github.com/{OWNER}/{repo["name"]}) | {repo["pushed_at"][:10]} |')
    return "\n".join(lines) if recent else "暂无近期公开项目更新。"


def main():
    repos = []
    for page in range(1, 101):
        batch = api(f"users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        repos.extend(public_owned(batch))
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("Repository pagination limit exceeded; preserve existing data.")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metrics = render_metrics(repos, date)
    readme = ROOT / "README.md"
    text = readme.read_text()
    start, end = "<!-- ACTIVITY:START -->", "<!-- ACTIVITY:END -->"
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise ValueError("README activity markers must appear exactly once, in order.")
    before, tail = text.split(start)
    _, after = tail.split(end)
    updated = f"{before}{start}\n{render_activity(repos)}\n{end}{after}"
    (ROOT / "assets" / "metrics.svg").write_text(metrics)
    readme.write_text(updated)
    print(f"Updated profile from {len(repos)} public repositories ({date}).")


if __name__ == "__main__":
    main()
