"""Generate docs/index.html from docs/case-study.md for GitHub Pages.

**Why generated rather than hand-written.** The case study would otherwise exist
twice — once as Markdown, once as HTML — and the two would drift. That is
CLAUDE.md rule 13 applied to prose: `docs/case-study.md` stays the single source,
and this produces the served page from it. Re-run after editing the case study.

**The output is self-contained by requirement.** No stylesheet, font, script or
image is fetched from outside the repository: the CSS is inlined and the type
stack is the reader's own system fonts. A page that needs a CDN is a page that
breaks when the CDN does, and it also leaks a request to whoever hosts it.

**Links out point at GitHub's rendered view, not at sibling files.** Pages serves
this directory statically (see `.nojekyll`), so a link to `credit-methodology.md`
would hand the reader raw Markdown. Absolute links to the repository render
properly instead.

Build dependency only — nothing in `src/` imports this, and the generated HTML is
committed, so a missing dependency fails here at build time and never at serve
time.

    .venv/bin/python docs/build_site.py
"""

import pathlib
import sys

try:
    from markdown_it import MarkdownIt
except ModuleNotFoundError:
    sys.exit("markdown-it-py is needed to build the site: "
             "pip install -e '.[docs]'")

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "case-study.md"
OUTPUT = ROOT / "index.html"
REPO = "https://github.com/ozairh-dev/credit-risk-analyser"
BLOB = f"{REPO}/blob/main"

# Links shown above the case study. Absolute, because Pages serves this folder
# statically and a relative .md link would download rather than render.
NAV = [
    ("Repository", REPO),
    ("Backtest results", f"{BLOB}/benchmark/results/a2_baseline.md"),
    ("Decision log", f"{BLOB}/DECISIONS.md"),
    ("Methodology", f"{BLOB}/docs/credit-methodology.md"),
    ("Scoring model", f"{BLOB}/docs/risk-scoring.md"),
    ("Architecture", f"{BLOB}/docs/architecture.md"),
]

TITLE = "Credit Risk Analyser — case study"
DESCRIPTION = (
    "A deterministic credit-risk analyser over SEC XBRL filings. Case study, "
    "including a point-in-time backtest against 18 companies that later filed "
    "Chapter 11."
)

CSS = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #5a5a5a; --rule: #e2e2e2;
  --code-bg: #f5f5f4; --accent: #7a1f1f; --quote: #f8f7f5;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16181a; --fg: #e6e4e1; --muted: #a2a09d; --rule: #2e3134;
    --code-bg: #21242700; --code-bg: #212427; --accent: #e0a0a0;
    --quote: #1d2022;
  }
}
:root[data-theme="dark"] {
  --bg: #16181a; --fg: #e6e4e1; --muted: #a2a09d; --rule: #2e3134;
  --code-bg: #212427; --accent: #e0a0a0; --quote: #1d2022;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  background: var(--bg); color: var(--fg); margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  font-size: 16px; line-height: 1.62;
}
.wrap { max-width: 46rem; margin: 0 auto; padding: 3rem 16px 6rem; }
nav { border-bottom: 1px solid var(--rule); padding-bottom: 1rem;
      margin-bottom: 2.5rem; font-size: 0.875rem; }
nav a { color: var(--muted); margin-right: 1.1rem; display: inline-block;
        white-space: nowrap; }
h1 { font-size: 1.9rem; line-height: 1.25; letter-spacing: -0.01em;
     margin: 0 0 1.5rem; }
h2 { font-size: 1.3rem; margin: 3rem 0 1rem; padding-bottom: 0.3rem;
     border-bottom: 1px solid var(--rule); letter-spacing: -0.005em; }
h3 { font-size: 1.05rem; margin: 2.2rem 0 0.75rem; }
p, ul, ol { margin: 0 0 1.1rem; }
li { margin-bottom: 0.35rem; }
a { color: var(--accent); text-decoration: underline;
    text-underline-offset: 2px; }
a:hover { text-decoration-thickness: 2px; }
strong { font-weight: 600; }
code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
               monospace;
  font-size: 0.86em; background: var(--code-bg); padding: 0.12em 0.34em;
  border-radius: 3px; overflow-wrap: break-word;
}
pre {
  background: var(--code-bg); padding: 0.9rem 1rem; border-radius: 4px;
  overflow-x: auto; font-size: 0.83rem; line-height: 1.5;
}
pre code { background: none; padding: 0; font-size: inherit; }
blockquote {
  margin: 1.4rem 0; padding: 0.85rem 1.1rem; background: var(--quote);
  border-left: 3px solid var(--accent); border-radius: 0 3px 3px 0;
}
blockquote p:last-child { margin-bottom: 0; }
.table-scroll { overflow-x: auto; margin: 0 0 1.3rem; }
table { border-collapse: collapse; font-size: 0.87rem; min-width: 100%; }
th, td { text-align: left; padding: 0.42rem 0.8rem 0.42rem 0;
         border-bottom: 1px solid var(--rule); vertical-align: top; }
th { font-weight: 600; white-space: nowrap; }
hr { border: 0; border-top: 1px solid var(--rule); margin: 2.5rem 0; }
footer { margin-top: 4rem; padding-top: 1.2rem;
         border-top: 1px solid var(--rule); color: var(--muted);
         font-size: 0.83rem; }
@media (max-width: 34rem) {
  .wrap { padding-top: 2rem; }
  h1 { font-size: 1.55rem; }
  nav a { margin-right: 0.9rem; }
}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>{css}</style>
</head>
<body>
<div class="wrap">
<nav>{nav}</nav>
{body}
<footer>
Generated from <code>docs/case-study.md</code> by <code>docs/build_site.py</code>.
Every figure on this page is reproducible from the repository.
</footer>
</div>
</body>
</html>
"""


def wrap_tables(html: str) -> str:
    """Let wide tables scroll instead of forcing the page wider than the phone."""
    return (html.replace("<table>", '<div class="table-scroll"><table>')
                .replace("</table>", "</table></div>"))


def main() -> int:
    if not SOURCE.exists():
        sys.exit(f"missing {SOURCE}")
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    body = wrap_tables(md.render(SOURCE.read_text(encoding="utf-8")))
    nav = " ".join(f'<a href="{url}">{label}</a>' for label, url in NAV)
    OUTPUT.write_text(TEMPLATE.format(
        title=TITLE, description=DESCRIPTION, css=CSS.strip(), nav=nav,
        body=body), encoding="utf-8")
    kb = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT.relative_to(ROOT.parent)} ({kb:.0f} KB) "
          f"from {SOURCE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
