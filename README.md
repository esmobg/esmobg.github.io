# esmobg.github.io

Personal page of **Ismail Ismail** (esmobg): WordPress developer and accessibility QA.
It lists all public GitHub projects in **Bulgarian** (default) and **English**.

- 🇧🇬 https://esmobg.github.io/
- 🇬🇧 https://esmobg.github.io/en/

The page is generated from the GitHub API by a GitHub Action **every day**, so new public repositories appear automatically.

## How it works

| Path | Purpose |
| --- | --- |
| `build.py` | Fetches the public repositories, merges `data/projects.json`, renders both languages into `_site/` (Python 3.9+, standard library only) |
| `templates/page.html` | The page template (`{{t.key}}` = translated text, `{{...}}` = generated blocks) |
| `i18n/bg.json`, `i18n/en.json` | All interface text. Both files must have the same keys (the build checks this) |
| `data/projects.json` | Per-project overrides: Bulgarian and English names and descriptions, order, group (`featured` or `archive`), tags, icon, live link, status |
| `assets/` | CSS (same design system as the [Accessibility Guardian website](https://esmobg.github.io/Accessibility-Guardian/)), theme-toggle script, monogram |
| `.github/workflows/pages.yml` | Builds and deploys on push, daily at 04:17 UTC, and on demand |

A new repository without an entry in `data/projects.json` is still shown: in **Featured** if it has content, or in **Learning & archive** if it is archived or empty. Its GitHub description is used in both languages until a translation is added.

## Add or update a project

Add an entry to `data/projects.json`:

```json
"my-repo": {
	"order": 8,
	"group": "featured",
	"icon": "code",
	"name": { "bg": "Моят проект", "en": "My project" },
	"description": { "bg": "Кратко описание.", "en": "Short description." },
	"tags": ["WordPress", "PHP"],
	"live": "https://example.com/"
}
```

Icons: `access`, `trophy`, `theme`, `radio`, `timer`, `cards`, `calculator`, `code`. Use `"hidden": true` to hide a repository.

## Preview locally

```bash
GITHUB_TOKEN=$(gh auth token) python build.py
python -m http.server 8000 --directory _site
# open http://127.0.0.1:8000/ and http://127.0.0.1:8000/en/
```

## Accessibility

The page targets **WCAG 2.2 AA** and is checked with axe-core in both languages, in light and dark themes, on desktop and mobile:
- correct `lang` attributes, including names and descriptions in the other language;
- skip link and landmarks;
- visible focus and AA contrast in both themes;
- targets of at least 44 px;
- no reliance on JavaScript;
- respects reduced-motion and forced-colours preferences.

---

# esmobg.github.io (на български)

Лична страница на **Исмаил Исмаил** (esmobg) – WordPress разработчик и консултант по достъпност. Показва всички публични проекти в GitHub на български (по подразбиране) и на английски. Страницата се генерира автоматично всеки ден от GitHub API, така че новите публични хранилища се появяват сами. Преводите на имената и описанията на проектите се добавят в `data/projects.json`, а текстовете на интерфейса – в `i18n/bg.json` и `i18n/en.json`.
