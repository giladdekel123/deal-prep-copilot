# Third-party notices

Status: prepared 21 November 2026 for the public portfolio version. This is a good-faith inventory, **not legal advice**. Where it
reports what a website's terms say, that was read by an automated fetch on 21 November 2026 and has not been confirmed by a lawyer.

**This repository's own material is licensed under the MIT License** (`LICENSE`). The MIT License does **not** apply to third-party content or
components; those keep their own terms, listed below. See "Licensing" at the end.

Nivarque Document Systems and Solquend Archive Systems are **fictional**. Every relationship, proposal, price and meeting described
between the fictional vendor and a real company is **synthetic**. The real companies named in this repository have no affiliation
with this project, have not reviewed it, and have not endorsed it. Company and product names may be trademarks of their owners.

## 1. Public-source knowledge base (`data/kb_v1/public/`)

In this public portfolio version, the statements of company websites and filings are **independently written summaries of publicly
stated facts** (names, years, figures). They are **not quotations** of the sources. Each file keeps its source URL, publisher,
publication date (or `unknown`), retrieval date and verification level, and says in its header that it is project-written content.
Where the corpus format puts text inside quotation marks, the stored text is the project's own sentence, and it is prefixed
"Summary:" where it would otherwise be displayed as a quotation attributed to the source.

| ID | Source page (publisher) | Retrieved | Content in this repository | Rights holder and terms found (21 Nov 2026, unconfirmed) |
|---|---|---|---|---|
| NVQ-PUB-001 | https://shikunbinui.com/en/history/ (Shikun & Binui) | 2026-11-05 | 3 summarized facts | Site terms (`/en/terms/`, section 3, as reported): copying or reproducing the site's content needs the company's prior written consent; a link is allowed. Not quoted here |
| NVQ-PUB-002 | https://shikunbinui.com/en/solel-boneh/ (Shikun & Binui) | 2026-11-05 | 2 summarized facts | Same |
| NVQ-PUB-003 | https://www.ashtrom.co.il/corporate-profile (Ashtrom Group) | 2026-11-05 | 5 summarized facts | Site terms (English version, section 4.3, as reported): no copying of site information without prior written permission. Not quoted here |
| NVQ-PUB-004 | https://www.arup.com/about-us/ (Arup) | 2026-11-05 | 2 summarized facts | Arup's legal pages were reported to contain no copying terms; footer "©Arup 2026". Not quoted here |
| NVQ-PUB-005 | https://www.arup.com/en-us/about-us/history/ (Arup) | 2026-11-05 | 2 summarized facts | As above |
| NVQ-PUB-006 | https://www.arup.com/en-us/careers/why-arup/ (Arup) | 2026-11-05 | 1 summarized fact | As above |
| NVQ-PUB-007 | Ove Arup & Partners International Limited, financial statements for the year ended 31 March 2024 (PDF on arup.com) | 2026-11-05 | 1 summarized fact | A company filing; no specific terms found. Not quoted here |

Facts themselves (for example a founding year) are not what these terms protect; the intent of the summaries is to reproduce facts in
the project's own words, not the sources' wording. The publishers may still have rights in their pages, and the owner has not asked any
of them for permission. If a rights holder objects, the corresponding file can be removed or replaced (see the tests and saved demo that
reference it, listed in the development notes).

### Wikipedia, NVQ-PUB-008 (quotations kept)

Five short quotations (about 42 words in total) from the English Wikipedia article "ARUP Laboratories"
(https://en.wikipedia.org/wiki/ARUP_Laboratories, revision of 19 October 2026, retrieved 2026-11-05) are kept **verbatim**, marked as
quotations, in `data/kb_v1/public/NVQ-PUB-008_arup_laboratories_wikipedia.md`. They are used to test name disambiguation (a real,
unrelated organization).

- **License:** Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/.
- **Attribution:** the article's authors are listed in its page history (https://en.wikipedia.org/wiki/ARUP_Laboratories?action=history).
- **Changes:** none; the quotations are unmodified fragments.
- **Share-alike:** applies to adaptations of that text. This file keeps its CC BY-SA 4.0 license; the repository's own code and synthetic
  material are separate works (see below).

## 2. Sample PDFs and screenshots (`portfolio/`)

- `portfolio/pdfs/AAL-*.pdf`, `DBS-*.pdf`: AI-drafted briefings from the final evaluation (20 November 2026), kept as generated. They
  cite public pages of Anglo American plc and DBS Group Holdings Ltd by URL and publication date, and mark synthetic records. A check on
  21 November 2026 found that they share **at most 10 consecutive words** with any passage of the sources they were drafted from (for
  example a short clause about copper ore grades); the remainder is short names and figures.
- `portfolio/pdfs/examples/saved_demo_*`: the offline saved demonstration, regenerated from the project-written summaries above.
- `portfolio/screenshots/`: the running offline app; no third-party passages.

## 3. Components not included (installed or downloaded by the user)

| Component | License (as declared) | Note |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` model | Apache-2.0 (model card) | Downloaded from Hugging Face by the user; not redistributed here |
| fpdf2 2.9.0 (PDF output) | LGPL-3.0-only | A direct dependency, used as an unmodified library and not bundled. Keep it as a separate install |
| chromadb 1.1.1, streamlit 1.67.0, sentence-transformers 3.3.1, transformers, openai, uharfbuzz 0.57.0, requests | Apache-2.0 | |
| torch 2.14.1 | BSD-style and other permissive licenses (declared as a combined expression) | |
| numpy, pypdf, pydantic, pytest, python-docx, openpyxl, httpx, python-dotenv, pillow | BSD, MIT or MIT-CMU | |
| certifi, orjson, tqdm | MPL-2.0 (transitive) | Not modified or bundled |
| Arial font | Microsoft | Read from the local Windows installation; not distributed |
| OpenAI and Tavily services | Their own terms | Optional paid APIs; keys are the user's own |

A scan of the 128 distributions installed in a fresh environment built from `requirements.txt` (21 November 2026) found no GPL, AGPL,
SSPL or non-commercial license. The copyleft-style entries are the LGPL fpdf2 and three MPL-2.0 transitive packages above.

## 4. Licensing

The owner chose the MIT License on 21 November 2026 for the project's own work. Scope:

- **MIT covers:** the original code, tests, scripts, documentation and the synthetic corpus (the fictional vendor's documents), which are the
  owner's own work. No bundled dependency imposes copyleft on them (fpdf2's LGPL applies to fpdf2, which is installed separately).
- **MIT does not cover:** the company names, trademarks and facts above (third-party), the Wikipedia quotations in `NVQ-PUB-008` (CC BY-SA 4.0,
  which keeps its own license), or the downloaded model, the Python packages and the fonts (their own licenses). The README says the same.
- The knowledge base summaries are the project's own wording of facts; the sources' rights holders keep their rights in their pages.

## 5. Historical records

Two historical records keep a short note from an earlier review, written when the saved demonstration still quoted a source (an
eight-word fragment): `eval/manual_checks_v1.json` and `docs/ACCEPTANCE_REPORT.md`. They are left unchanged because they record what a
reviewer saw on a given date. The current saved demonstration no longer contains that wording.

## 6. Removal requests

If you are a rights holder and want content removed or changed, open an issue in this repository or contact the owner through the owner's GitHub
profile, https://github.com/giladdekel123. (No e-mail address is published.) Material will be reviewed promptly.
