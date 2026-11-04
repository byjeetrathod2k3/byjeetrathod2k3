#!/usr/bin/env python3
"""Generate GitHub stats cards as static SVGs (midnight palette).

Reads public data for GH_USER through the GitHub GraphQL API using GITHUB_TOKEN
and writes four files to OUT_DIR:
  stats-overview.svg, languages.svg, streak.svg, activity.svg

Standard library only. Run with --mock to render sample data without network.
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from xml.sax.saxutils import escape as esc

BG0, BG1, BG2 = "#080D19", "#0D1728", "#102A46"
A0, A1, A2 = "#0879C9", "#278CEB", "#55B9FF"
TXT, MUTED = "#E6EEF8", "#8FA6BF"
DISPLAY = "'Space Grotesk','Inter','Segoe UI',Helvetica,Arial,sans-serif"
BODY = "'Inter','Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {payload.get('errors')}")
    return payload["data"]["user"]


def mock():
    random.seed(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    days = []
    for i in range(365):
        d = start + dt.timedelta(days=i)
        days.append({"date": d.isoformat(), "contributionCount": random.choice([0, 0, 0, 1, 2, 4, 7])})
    weeks = [{"contributionDays": days[i:i + 7]} for i in range(0, 365, 7)]
    return {
        "followers": {"totalCount": 3},
        "repositories": {"totalCount": 9, "nodes": [
            {"stargazerCount": 2, "languages": {"edges": [
                {"size": 52000, "node": {"name": "Python"}}, {"size": 31000, "node": {"name": "Dart"}},
                {"size": 18000, "node": {"name": "HTML"}}, {"size": 9000, "node": {"name": "Jupyter Notebook"}},
                {"size": 4000, "node": {"name": "TypeScript"}}]}}]},
        "contributionsCollection": {
            "totalCommitContributions": 143, "totalPullRequestContributions": 6, "totalIssueContributions": 2,
            "contributionCalendar": {"totalContributions": sum(d["contributionCount"] for d in days), "weeks": weeks}},
    }


def head(w, h, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="t d">\n<title id="t">{esc(title)}</title>\n<desc id="d">{esc(desc)}</desc>\n'
            f'<rect width="{w}" height="{h}" rx="6" fill="{BG1}" stroke="{BG2}"/>\n'
            f'<rect x="0" y="0" width="4" height="{h}" rx="2" fill="{A1}"/>\n')


def card_title(text):
    return f'<text x="28" y="38" font-family="{DISPLAY}" font-size="17" font-weight="600" fill="{A2}">{esc(text)}</text>\n'


def fmt(n):
    return f"{n:,}"


def overview(u):
    cc = u["contributionsCollection"]
    rows = [
        ("Contributions, last 12 months", cc["contributionCalendar"]["totalContributions"]),
        ("Commits", cc["totalCommitContributions"]),
        ("Pull requests", cc["totalPullRequestContributions"]),
        ("Issues", cc["totalIssueContributions"]),
        ("Public repositories", u["repositories"]["totalCount"]),
        ("Stars earned", sum(n["stargazerCount"] for n in u["repositories"]["nodes"])),
        ("Followers", u["followers"]["totalCount"]),
    ]
    w, h = 430, 236
    s = head(w, h, "GitHub statistics", "; ".join(f"{k}: {v}" for k, v in rows)) + card_title("GitHub statistics")
    for i, (k, v) in enumerate(rows):
        y = 74 + i * 25
        s += (f'<text x="28" y="{y}" font-family="{BODY}" font-size="13.5" fill="{MUTED}">{esc(k)}</text>'
              f'<text x="{w-28}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" fill="{TXT}">{fmt(v)}</text>\n')
    return s + "</svg>\n"


def languages(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            totals[e["node"]["name"]] = totals.get(e["node"]["name"], 0) + e["size"]
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    total = sum(totals.values()) or 1
    w, h = 430, 236
    desc = "; ".join(f"{k}: {v*100/total:.1f}%" for k, v in top) or "No language data yet"
    s = head(w, h, "Most used languages", desc) + card_title("Most used languages")
    if not top:
        return s + f'<text x="28" y="80" font-family="{BODY}" font-size="13.5" fill="{MUTED}">No language data yet.</text></svg>\n'
    shades = [A2, A1, A0, "#1F6FB0", "#1B5A91", "#17476F"]
    bar_w = w - 56
    for i, (k, v) in enumerate(top):
        y = 68 + i * 27
        pct = v * 100 / total
        s += (f'<text x="28" y="{y}" font-family="{BODY}" font-size="13" fill="{TXT}">{esc(k)}</text>'
              f'<text x="{w-28}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">{pct:.1f}%</text>'
              f'<rect x="28" y="{y+6}" width="{bar_w}" height="5" rx="2.5" fill="{BG2}"/>'
              f'<rect x="28" y="{y+6}" width="{max(bar_w*pct/100, 3):.1f}" height="5" rx="2.5" fill="{shades[i]}"/>\n')
    return s + "</svg>\n"


def streaks(days):
    cur = best = run = 0
    best_end = cur_start = None
    best_start = run_start = None
    prev = None
    for d in days:
        if d["count"] > 0:
            if prev is not None and (d["date"] - prev).days == 1 and run > 0:
                run += 1
            else:
                run, run_start = 1, d["date"]
            if run > best:
                best, best_start, best_end = run, run_start, d["date"]
            prev = d["date"]
        else:
            run = 0
            prev = d["date"]
    # current streak: walk back from the latest day; today may still be empty
    idx = len(days) - 1
    if idx >= 0 and days[idx]["count"] == 0:
        idx -= 1
    end = days[idx]["date"] if idx >= 0 else None
    while idx >= 0 and days[idx]["count"] > 0:
        cur += 1
        cur_start = days[idx]["date"]
        idx -= 1
    return cur, (cur_start, end), best, (best_start, best_end)


def rng(a, b):
    f = lambda d: f"{d.strftime('%b')} {d.day}, {d.year}"
    return f"{f(a)} - {f(b)}" if a and b else "No streak yet"


def streak_card(days, total):
    cur, cur_r, best, best_r = streaks(days)
    w, h = 860, 150
    desc = (f"Current streak {cur} days. Total contributions {total} in the last 12 months. "
            f"Longest streak in that period {best} days.")
    s = head(w, h, "Contribution streak", desc)
    cols = [(w * 1 / 6, str(cur), "Current streak (days)", rng(*cur_r) if cur else "No active streak"),
            (w * 3 / 6, fmt(total), "Contributions, last 12 months", f"{days[0]['date']:%b %-d, %Y} - {days[-1]['date']:%b %-d, %Y}"),
            (w * 5 / 6, str(best), "Longest streak (days), last 12 months", rng(*best_r) if best else "No streak yet")]
    for i, (x, big, label, sub) in enumerate(cols):
        s += (f'<text x="{x:.0f}" y="70" text-anchor="middle" font-family="{DISPLAY}" font-size="40" font-weight="700" fill="{TXT}">{big}</text>'
              f'<text x="{x:.0f}" y="96" text-anchor="middle" font-family="{BODY}" font-size="13" font-weight="600" fill="{A2}">{esc(label)}</text>'
              f'<text x="{x:.0f}" y="118" text-anchor="middle" font-family="{BODY}" font-size="12" fill="{MUTED}">{esc(sub)}</text>\n')
        if i:
            s += f'<line x1="{w*i/3:.0f}" y1="28" x2="{w*i/3:.0f}" y2="{h-28}" stroke="{BG2}"/>\n'
    return s + "</svg>\n"


def activity_card(weeks_raw):
    sums = []
    labels = []
    for wk in weeks_raw:
        ds = wk["contributionDays"]
        sums.append(sum(d["contributionCount"] for d in ds))
        d0 = dt.date.fromisoformat(ds[0]["date"])
        labels.append(d0)
    w, h = 860, 230
    x0, x1, y0, y1 = 52, w - 28, 62, h - 44
    peak = max(max(sums), 1)
    n = len(sums)
    step = (x1 - x0) / max(n - 1, 1)
    pts = [(x0 + i * step, y1 - (v / peak) * (y1 - y0)) for i, v in enumerate(sums)]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area = line + f" L{x1} {y1} L{x0} {y1} Z"
    desc = f"Weekly contributions over the last 12 months. Total {sum(sums)}. Busiest week {peak}."
    s = head(w, h, "Contribution activity", desc) + card_title("Contribution activity, last 12 months")
    s += (f'<defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{A1}" stop-opacity=".45"/>'
          f'<stop offset="1" stop-color="{A1}" stop-opacity="0"/></linearGradient></defs>\n')
    for frac in (0, .5, 1):
        gy = y1 - frac * (y1 - y0)
        s += (f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" stroke="{BG2}"/>'
              f'<text x="{x0-8}" y="{gy+4:.1f}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">{round(peak*frac)}</text>\n')
    s += f'<path d="{area}" fill="url(#ar)"/><path d="{line}" fill="none" stroke="{A2}" stroke-width="2" stroke-linejoin="round"/>\n'
    last_m = None
    for i, d in enumerate(labels):
        if d.month != last_m and (x0 + i * step) < x1 - 24:
            s += f'<text x="{x0+i*step:.1f}" y="{h-18}" font-family="{MONO}" font-size="11" fill="{MUTED}">{d:%b}</text>'
        last_m = d.month
    s += f'<text x="{w-28}" y="38" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">contributions per week</text>\n'
    return s + "</svg>\n"


def main():
    out = os.environ.get("OUT_DIR", "dist")
    os.makedirs(out, exist_ok=True)
    if "--mock" in sys.argv:
        u = mock()
    else:
        login, token = os.environ.get("GH_USER"), os.environ.get("GITHUB_TOKEN")
        if not login or not token:
            raise SystemExit("GH_USER and GITHUB_TOKEN must be set")
        u = fetch(login, token)
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [{"date": dt.date.fromisoformat(d["date"]), "count": d["contributionCount"]}
            for wk in weeks for d in wk["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    total = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    files = {
        "stats-overview.svg": overview(u),
        "languages.svg": languages(u),
        "streak.svg": streak_card(days, total),
        "activity.svg": activity_card(weeks),
    }
    for name, content in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("wrote", name, len(content), "bytes")


if __name__ == "__main__":
    main()
