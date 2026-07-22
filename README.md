# Lab documentation site (`gh-pages`)

This branch holds the **participant-facing lab documentation** and the tooling
that builds it. GitHub Pages serves `index.html` from the root of this branch.

> The `main` branch is different: it's what the tutorial participant downloads
> (the agent skills). Docs live here on `gh-pages` only.

## How the site is built

The site is a **single self-contained `index.html`** — the lab markdown and the
`marked.js` renderer are inlined into one file with no runtime fetches.

Everything that produces it lives in `site/`:

```
site/
├── Gemini World 3 QwikLab 2.0.md   ← the source you edit
├── index.html                      ← HTML template (has the md-inline placeholder)
├── marked.min.js                   ← markdown renderer (vendored)
└── build.py                        ← inlines the md + renderer into ../index.html
index.html                          ← the built file GitHub Pages serves (do NOT hand-edit)
images/                             ← screenshots referenced by the markdown
```

## To update the docs

1. Edit the source markdown: **`site/Gemini World 3 QwikLab 2.0.md`**
   (add screenshots to `images/` and reference them with relative paths, e.g.
   `![](images/my-screenshot.png)`).
2. Rebuild the served file:
   ```bash
   python3 site/build.py
   ```
   This regenerates the root **`index.html`**.
3. Commit both the markdown and the rebuilt `index.html`, then push:
   ```bash
   git add -A && git commit -m "Update lab docs" && git push origin gh-pages
   ```

## Important

- **Never hand-edit the root `index.html`.** It's generated. Edit the markdown in
  `site/` and re-run `build.py`, otherwise the source and the live site drift
  apart.
- To preview locally before pushing, open the built file directly
  (`open index.html`) or serve it: `python3 -m http.server 8000` then visit
  http://localhost:8000.
