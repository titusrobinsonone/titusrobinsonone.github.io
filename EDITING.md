# Maintain your portfolio

Your public address is **https://titusrobinsonone.github.io/**. Everything needed to display it lives in this repository. GitHub Pages publishes the `docs` directory from `main`.

## Change your introduction or contact links

1. Open [docs/site.json](https://github.com/titusrobinsonone/titusrobinsonone.github.io/blob/main/docs/site.json).
2. Click GitHub’s pencil / **Edit this file** control.
3. Change the text inside the quotation marks. Keep the commas and braces intact.
4. Click **Commit changes**. The Pages deployment will update the live site.

The name, intro, location, About paragraph, contact text, LinkedIn link and GitHub link are all in that file. Do not put private contact information there unless you want it public.

## Add a project without writing website code

1. Upload a thumbnail into [docs/assets](docs/assets). A 760 × 500 SVG or PNG works well. Use a lowercase filename without spaces.
2. Open [docs/projects.json](https://github.com/titusrobinsonone/titusrobinsonone.github.io/blob/main/docs/projects.json).
3. Copy an existing project object or the template below. Add it inside the outer `[` and `]`, separated from the previous object by a comma.
4. Give it a unique `id`, set the text and links, and commit. Its card, category filter and case-study page appear automatically. Array order controls gallery order.

```json
{
  "id": "new-project",
  "number": "06",
  "title": "A clear, memorable project headline.",
  "name": "Descriptive Project Name",
  "category": "Business intelligence",
  "summary": "A short explanation of the problem and the useful tool or analysis.",
  "question": "What business decision does this project help answer?",
  "thumbnail": "assets/new-project.png",
  "tags": ["Python", "SQL"],
  "proof": "A specific, verified feature or result",
  "demo": "https://your-github-pages-demo.github.io/",
  "source": "https://github.com/your-account/your-project",
  "download": "assets/new-project.zip",
  "problem": "Who has the problem, and why does it matter?",
  "approach": ["First analytical step.", "Second analytical step."],
  "finding": "What the actual analysis shows, with appropriate context.",
  "validation": ["A meaningful check or test."],
  "limitations": "Assumptions, uncertainty and what the project cannot establish.",
  "run": "python your_script.py",
  "methods": []
}
```

Use genuine file/link destinations; replace every template value before publishing. `demo` may be another GitHub Pages URL or a file such as `my-dashboard.html`. `download` should link to a real ZIP or PDF. Preserve the synthetic-data context unless the project uses another clearly documented source.

`demoType` and `data` are only needed for the three built-in interactive engines (`inventory`, `revenue`, `experiment`). A normal future case study needs neither: its **Open the demo** button uses `demo`.

The automatic case-study URL will be `https://titusrobinsonone.github.io/project.html?id=new-project`.

## Reorder, hide or revise an existing project

- Move an object up or down in the JSON array to reorder it.
- Remove an object to hide it from the gallery; the underlying source files stay in Git history.
- Edit `title`, `summary`, `approach`, `finding` and `limitations` to improve the case study.
- A new `category` automatically creates a new filter.
- Keep IDs stable if you have shared case-study URLs.

## Validate before publishing larger changes

Run `python src/validate_portfolio.py` and the checks in the root README. For content-only edits, validate the JSON and check that thumbnails, downloads and source links exist. Preview locally with `python -m http.server 8000 --directory docs`.

After committing, GitHub **Actions → pages build and deployment** should finish successfully. Refresh the public page once the deployment completes. If needed, revert the commit through GitHub to restore the prior version.

## Design and attribution

The layout takes inspiration from the clean editorial gallery in the supplied reference. Its code, monogram, charts and project presentation are independent. No reference-site portrait, logo, article or proprietary data is used.

Titus Robinson is the portfolio owner and maintainer. The projects were created with AI-assisted implementation, and their credibility rests on reproducible source, explicit assumptions and verified behavior. Do not present synthetic results as production savings or client outcomes.
