#!/usr/bin/env python3
"""Build the single self-contained index.html that GitHub Pages serves.

Inlines marked.min.js and the lab markdown into one file with no runtime
fetches, then writes it to the repo-root index.html on the gh-pages branch
(the file GitHub Pages actually serves). Edit the markdown, run this, commit.

Usage:
  python3 site/build.py           # build once
  python3 site/build.py --watch   # rebuild automatically whenever a source
                                   # file changes (Ctrl-C to stop)

Output: ../index.html  (repo root, served by GitHub Pages)
"""

import sys
import time
import pathlib

here = pathlib.Path(__file__).parent  # site/
root = here.parent  # gh-pages repo root

md_path = here / "Gemini World 3 QwikLab 2.0.md"
tpl_path = here / "index.html"
marked_path = here / "marked.min.js"
out_path = root / "index.html"  # the file GitHub Pages serves

# The files whose changes should trigger a rebuild in --watch mode.
SOURCES = [md_path, tpl_path, marked_path]


def build():
    """Assemble the self-contained index.html and write it to the repo root."""
    html = tpl_path.read_text()
    marked_js = marked_path.read_text()
    md = md_path.read_text()

    # Prevent the markdown from prematurely closing the inline <script> tag.
    md_safe = md.replace("</script>", "<\\/script>")

    # Inline marked.js (replace the external <script src>).
    assert '<script src="marked.min.js"></script>' in html, (
        "marked script tag not found"
    )
    html = html.replace(
        '<script src="marked.min.js"></script>',
        "<script>\n" + marked_js + "\n</script>",
    )

    # Inject the markdown into the inline placeholder.
    placeholder = '<script type="text/markdown" id="md-inline"></script>'
    assert placeholder in html, "md-inline placeholder not found"
    html = html.replace(
        placeholder,
        '<script type="text/markdown" id="md-inline">\n' + md_safe + "\n</script>",
    )

    out_path.write_text(html)
    return len(html)


def watch(interval=0.5):
    """Rebuild whenever a source file's mtime changes. Ctrl-C to stop."""

    def snapshot():
        return {p: p.stat().st_mtime for p in SOURCES if p.exists()}

    size = build()
    print(f"Wrote {out_path} ({size:,} bytes)")
    print(f"Watching for changes in {here}/ … (Ctrl-C to stop)")
    last = snapshot()
    try:
        while True:
            time.sleep(interval)
            now = snapshot()
            if now != last:
                last = now
                try:
                    size = build()
                    stamp = time.strftime("%H:%M:%S")
                    print(f"[{stamp}] rebuilt {out_path.name} ({size:,} bytes)")
                except Exception as e:  # keep watching even if a build fails
                    print(f"build error: {e}")
    except KeyboardInterrupt:
        print("\nStopped watching.")


if __name__ == "__main__":
    if "--watch" in sys.argv[1:]:
        watch()
    else:
        size = build()
        print(f"Wrote {out_path} ({size:,} bytes)")
