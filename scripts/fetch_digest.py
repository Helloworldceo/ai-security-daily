"""Daily AI/LLM security digest.

Pulls the newest arXiv papers on LLM security topics (prompt injection,
jailbreaks, agent security, data poisoning ...), skips ones already logged,
and writes a dated Markdown digest plus an updated README.
"""
import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"
SEEN = ROOT / "data" / "seen.json"
README = ROOT / "README.md"

QUERY = (
    'all:"prompt injection" OR all:jailbreak OR all:"LLM security" '
    'OR all:"agent security" OR all:"red teaming" OR all:"data poisoning" '
    'OR all:"adversarial prompt"'
)
MAX_RESULTS = 40
PER_DAY = 10
NS = {"a": "http://www.w3.org/2005/Atom"}


def fetch():
    params = urllib.parse.urlencode({
        "search_query": f"cat:cs.CR AND ({QUERY})",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": MAX_RESULTS,
    })
    url = f"https://export.arxiv.org/api/query?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-security-daily/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        root = ET.fromstring(r.read())
    papers = []
    for e in root.findall("a:entry", NS):
        pid = e.findtext("a:id", "", NS).rsplit("/", 1)[-1].split("v")[0]
        papers.append({
            "id": pid,
            "title": " ".join(e.findtext("a:title", "", NS).split()),
            "authors": [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)],
            "published": e.findtext("a:published", "", NS)[:10],
            "summary": " ".join(e.findtext("a:summary", "", NS).split()),
            "url": f"https://arxiv.org/abs/{pid}",
        })
    return papers


def short(text, n=280):
    return text if len(text) <= n else text[: n].rsplit(" ", 1)[0] + "…"


def main():
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    DIGESTS.mkdir(exist_ok=True)
    SEEN.parent.mkdir(exist_ok=True)
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()

    try:
        papers = fetch()
        error = None
    except Exception as exc:  # network hiccup: still log the run
        papers, error = [], str(exc)

    new = [p for p in papers if p["id"] not in seen][:PER_DAY]
    seen.update(p["id"] for p in new)
    SEEN.write_text(json.dumps(sorted(seen), indent=0))

    out = DIGESTS / f"{today}.md"
    if out.exists() and not new:
        lines = None  # re-run with nothing new: keep today's digest as is
    else:
        lines = [f"# AI Security Digest — {today}", ""]
        if out.exists():  # re-run the same day: keep earlier entries
            lines = out.read_text().replace(
                "_No new matching papers since the last digest._\n", "").splitlines()
            if lines and lines[-1] != "":
                lines.append("")
        elif error:
            lines += [f"_arXiv fetch failed today: {error}_", ""]
        elif not new:
            lines += ["_No new matching papers since the last digest._", ""]
    for p in new:
        authors = ", ".join(p["authors"][:4]) + (" et al." if len(p["authors"]) > 4 else "")
        lines += [
            f"## [{p['title']}]({p['url']})",
            f"*{authors}* · submitted {p['published']}",
            "",
            short(p["summary"]),
            "",
        ]
    if lines is not None:
        out.write_text("\n".join(lines))

    files = sorted(DIGESTS.glob("*.md"), reverse=True)
    recent = "\n".join(f"- [{f.stem}](digests/{f.name})" for f in files[:14])
    README.write_text(
        "# AI Security Daily\n\n"
        "An automated daily digest of new arXiv research on AI/LLM security: prompt injection, "
        "jailbreaks, agent and RAG security, red-teaming and data poisoning.\n\n"
        "A GitHub Action runs every day, queries arXiv (cs.CR), skips papers already covered, "
        "and commits a dated digest to [`digests/`](digests/).\n\n"
        f"**Papers tracked so far:** {len(seen)} · **Last run:** {today}\n\n"
        "## Recent digests\n\n"
        f"{recent}\n\n"
        "---\nMaintained by [@Helloworldceo](https://github.com/Helloworldceo) · "
        "companion to [AI-Agent-Red-Team](https://github.com/Helloworldceo/AI-Agent-Red-Team)\n"
    )
    print(f"{today}: {len(new)} new papers, {len(seen)} tracked")


if __name__ == "__main__":
    main()
