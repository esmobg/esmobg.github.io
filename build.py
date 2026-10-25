#!/usr/bin/env python3
"""Build esmobg.github.io: a bilingual (BG/EN) page listing all public GitHub projects.

Usage:
    python build.py                         # fetch repos from the GitHub API, write _site/
    python build.py --out _site --repos-file repos.json   # use a saved API response
    python build.py --save-repos repos.json # also save the API response

Set GITHUB_TOKEN (or GH_TOKEN) to avoid API rate limits. Python 3.9+, standard library only.

Output:
    _site/index.html      Bulgarian (default language)
    _site/en/index.html   English
    _site/404.html, robots.txt, sitemap.xml, assets/
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import struct
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USER = "esmobg"
SITE_URL = f"https://{USER}.github.io/"
LANGS = ("bg", "en")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Small inline icons (24x24, stroke-based, decorative).
ICONS = {
    "access": '<circle cx="12" cy="4.5" r="2" fill="currentColor" stroke="none"/><path d="M5 8.5l7 1.5 7-1.5M12 10v5m0 0-3 6m3-6 3 6"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0V4zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4m-4 3h8m-6-3h4"/>',
    "theme": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>',
    "radio": '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8l9-5"/><circle cx="15" cy="14" r="3"/><path d="M6.5 12.5h2m-2 3h2"/>',
    "timer": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M10 2h4M12 2v3"/>',
    "cards": '<rect x="4" y="5" width="11" height="15" rx="2"/><path d="M9 3.5h9a2 2 0 0 1 2 2V18"/><path d="M9.5 10.5l1.2-2.5 1.2 2.5 2.6.4-1.9 1.8.5 2.6-2.4-1.3-2.4 1.3.5-2.6-1.9-1.8z" fill="currentColor" stroke="none"/>',
    "calculator": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>',
}


def icon_svg(name: str, size: int = 26) -> str:
    paths = ICONS.get(name, ICONS["code"])
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{paths}</svg>'
    )


def inline_svg(name: str, css_class: str) -> str:
    """Inline an SVG from assets/img as decorative markup that inherits currentColor."""
    svg = (ROOT / "assets" / "img" / name).read_text(encoding="utf-8").strip()
    svg = re.sub(r'\s(role|aria-label)="[^"]*"', "", svg, count=2)
    return svg.replace("<svg ", f'<svg class="{css_class}" aria-hidden="true" focusable="false" ', 1)


def png_size(path: str) -> tuple[int, int]:
    """Width and height of a PNG in the repository, read from its header."""
    header = (ROOT / path).read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path} is not a PNG")
    return struct.unpack(">II", header[16:24])


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fetch_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    while True:
        request = urllib.request.Request(
            f"https://api.github.com/users/{USER}/repos?type=owner&sort=pushed&per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-site-build"},
        )
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def format_date(iso: str, t: dict) -> str:
    date = dt.date.fromisoformat(iso[:10])
    return t["date_format"].format(d=date.day, month=t["months"][date.month - 1], y=date.year)


def lang_attr(text: str, page_lang: str) -> str:
    """lang attribute for text in the other language (helps screen readers pronounce it)."""
    has_cyrillic = bool(CYRILLIC.search(text))
    if page_lang == "bg" and not has_cyrillic and re.search(r"[A-Za-z]", text):
        return ' lang="en"'
    if page_lang == "en" and has_cyrillic:
        return ' lang="bg"'
    return ""


def localized(value: object, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    return str(value or "")


def collect(repos: list[dict], overrides: dict) -> list[dict]:
    projects = []
    for index, repo in enumerate(repos):
        name = repo.get("name", "")
        if repo.get("fork") or repo.get("private") or name.lower() == f"{USER}.github.io":
            continue
        meta = overrides.get(name, {})
        if meta.get("hidden"):
            continue

        size = int(repo.get("size") or 0)
        description = (repo.get("description") or "").strip()
        archived = bool(repo.get("archived"))
        auto_archive = archived or size == 0 or (not description and size < 5)
        status = meta.get("status") or ("archived" if archived else "empty" if size == 0 else "")

        tags = meta.get("tags")
        if not tags:
            tags = ([repo["language"]] if repo.get("language") else []) + list(repo.get("topics") or [])
        license_id = ((repo.get("license") or {}).get("spdx_id") or "").strip()

        projects.append(
            {
                "repo": name,
                "url": repo.get("html_url") or f"https://github.com/{USER}/{name}",
                "group": meta.get("group") or ("archive" if auto_archive else "featured"),
                "order": meta.get("order", 100 + index),
                "name": meta.get("name") or {lang: name for lang in LANGS},
                "description": meta.get("description") or {lang: description for lang in LANGS},
                "tags": list(dict.fromkeys(tags))[:5],
                "icon": meta.get("icon") or "code",
                "logo": meta.get("logo") or "",
                "live": meta.get("live") or (repo.get("homepage") or "").strip(),
                "live_label": meta.get("live_label", "live"),
                "status": status,
                "license": "" if license_id in ("", "NOASSERTION", "NONE") else license_id,
                "stars": int(repo.get("stargazers_count") or 0),
                "language": repo.get("language") or "",
                "pushed_at": repo.get("pushed_at") or repo.get("updated_at") or "",
            }
        )
    return sorted(projects, key=lambda p: (p["order"], p["repo"].lower()))


def render_card(project: dict, lang: str, t: dict) -> str:
    name = localized(project["name"], lang)
    description = localized(project["description"], lang)
    slug = re.sub(r"[^a-z0-9]+", "-", project["repo"].lower()).strip("-")
    name_lang = lang_attr(name, lang)

    tags = "".join(f"<li{lang_attr(tag, lang)}>{esc(tag)}</li>" for tag in project["tags"])
    meta_parts = []
    if project["pushed_at"]:
        meta_parts.append(f'{esc(t["updated"])} <time datetime="{esc(project["pushed_at"][:10])}">{esc(format_date(project["pushed_at"], t))}</time>')
    if project["license"]:
        meta_parts.append(f'{esc(t["license"])} <span lang="en">{esc(project["license"])}</span>')
    if project["stars"] > 0:
        word = t["star"] if project["stars"] == 1 else t["stars"]
        meta_parts.append(f'{project["stars"]} {esc(word)}')
    meta = " · ".join(meta_parts)

    links = []
    live = localized(project["live"], lang)
    if live:
        label = t["website"] if project["live_label"] == "website" else t["live"]
        suffix = t["live_suffix"].format(name=name)
        links.append(
            f'<a class="button-sm button-sm--primary" href="{esc(live)}">{esc(label)}'
            f'<span class="visually-hidden"> {esc(suffix)}</span></a>'
        )
    code_suffix = t["code_suffix"].format(name=name)
    links.append(
        f'<a class="button-sm" href="{esc(project["url"])}">{esc(t["code"])}'
        f'<span class="visually-hidden"> {esc(code_suffix)}</span></a>'
    )

    # A project's own logo replaces the generic icon. PNGs are made for 2x screens.
    logo = ""
    icon = f'<span class="project__icon">{icon_svg(project["icon"])}</span>'
    if project["logo"]:
        width, height = png_size(project["logo"])
        logo = f'''
							<div class="project__logo"><img src="/{esc(project["logo"])}" width="{width // 2}" height="{height // 2}" alt="" loading="lazy"></div>'''
        icon = ""

    return f"""<li>
						<article class="project" aria-labelledby="project-{slug}">{logo}
							<div class="project__head">
								{icon}<h3 id="project-{slug}"{name_lang}>{esc(name)}</h3>
							</div>
							<p class="project__desc"{lang_attr(description, lang)}>{esc(description)}</p>
							<ul class="tags" aria-label="{esc(t["technologies"])}">{tags}</ul>
							<p class="project__meta">{meta}</p>
							<div class="project__links">{"".join(links)}</div>
						</article>
					</li>"""


def render_archive_item(project: dict, lang: str, t: dict) -> str:
    name = localized(project["name"], lang)
    description = localized(project["description"], lang)
    status = t.get(f"status_{project['status']}", "") if project["status"] else ""
    badge = f' <span class="archive__status">{esc(status)}</span>' if status else ""
    code_suffix = t["code_suffix"].format(name=name)
    return f"""<li>
						<a class="archive__link" href="{esc(project["url"])}"><span{lang_attr(name, lang)}>{esc(name)}</span><span class="visually-hidden"> – {esc(t["code"])} {esc(code_suffix)}</span></a>{badge}
						<span class="archive__desc"{lang_attr(description, lang)}>{esc(description)}</span>
					</li>"""


def render_stats(projects: list[dict], lang: str, t: dict) -> str:
    total = len(projects)
    live = sum(1 for p in projects if localized(p["live"], lang))
    languages = len({p["language"] for p in projects if p["language"]})
    items = [
        (str(total), t["stat_projects"]),
        (str(live), t["stat_live"]),
        (str(languages), t["stat_languages"]),
        ("AA", t["stat_focus"]),
    ]
    return "\n\t\t\t\t".join(
        f'<li><strong class="stat__value">{esc(value)}</strong> <span>{esc(label)}</span></li>' for value, label in items
    )


def render_page(template: str, context: dict, t: dict) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key.startswith("t."):
            name = key[2:]
            if name not in t:
                raise KeyError(f"missing translation key: {name}")
            value = t[name]
            return str(value) if name.endswith("_html") else esc(value)
        if key not in context:
            raise KeyError(f"missing template value: {key}")
        return str(context[key])

    page = re.sub(r"\{\{\s*([a-z0-9_.]+)\s*\}\}", replace, template)
    if "{{" in page:
        raise ValueError("unreplaced template placeholder")
    return page


NOT_FOUND = """<!doctype html>
<html lang="bg">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
	<meta name="referrer" content="strict-origin-when-cross-origin">
	<title>{bg_title} / {en_title}</title>
	<meta name="robots" content="noindex">
	<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
	<script src="/assets/js/theme-init.js"></script>
	<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
	<main id="content" class="final-cta not-found">
		<div class="container container--narrow">
			{logo}
			<h1>{bg_title} <span lang="en">/ {en_title}</span></h1>
			<p>{bg_text}</p>
			<p lang="en">{en_text}</p>
			<div class="cta cta--center">
				<a class="button button--primary" href="/">{bg_home}</a>
				<a class="button button--primary" href="/en/" lang="en">{en_home}</a>
			</div>
		</div>
	</main>
</body>
</html>
"""


# The plugin website moved when "Accessibility Guardian" became "Esmo Accessibility Scanner"
# (repository renamed). GitHub Pages cannot redirect, so its old addresses get small pages that do.
MOVED_PAGES = {
    "Accessibility-Guardian": ("en", "https://esmobg.github.io/Esmo-Accessibility-Scanner/"),
    "Accessibility-Guardian/bg": ("bg", "https://esmobg.github.io/Esmo-Accessibility-Scanner/bg/"),
}

MOVED = """<!doctype html>
<html lang="{lang}">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
	<meta name="referrer" content="strict-origin-when-cross-origin">
	<meta http-equiv="refresh" content="0; url={url}">
	<meta name="robots" content="noindex">
	<link rel="canonical" href="{url}">
	<title>{title}</title>
	<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
	<script src="/assets/js/theme-init.js"></script>
	<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
	<main id="content" class="final-cta not-found">
		<div class="container container--narrow">
			<h1>{title}</h1>
			<p>{text}</p>
			<div class="cta cta--center">
				<a class="button button--primary" href="{url}">{link}</a>
			</div>
		</div>
	</main>
</body>
</html>
"""

MOVED_TEXT = {
    "en": {
        "title": "Accessibility Guardian is now Esmo Accessibility Scanner",
        "text": "The plugin has a new name and its website a new address. You are being taken there now.",
        "link": "Go to Esmo Accessibility Scanner",
    },
    "bg": {
        "title": "Accessibility Guardian вече е Esmo Accessibility Scanner",
        "text": "Плъгинът има ново име, а сайтът му – нов адрес. Пренасочваме ви натам.",
        "link": "Към Esmo Accessibility Scanner",
    },
}


def write_moved_pages(out: Path) -> None:
    for path, (lang, url) in MOVED_PAGES.items():
        target = out / path / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        words = MOVED_TEXT[lang]
        target.write_text(
            MOVED.format(lang=lang, url=esc(url), title=esc(words["title"]), text=esc(words["text"]), link=esc(words["link"])),
            encoding="utf-8",
            newline="\n",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="_site")
    parser.add_argument("--repos-file", help="Read repositories from this JSON file instead of the API.")
    parser.add_argument("--save-repos", help="Save the API response to this JSON file.")
    args = parser.parse_args()

    translations = {lang: json.loads((ROOT / "i18n" / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}
    if set(translations["bg"]) != set(translations["en"]):
        sys.exit(f"Translation keys differ: {sorted(set(translations['bg']) ^ set(translations['en']))}")

    overrides = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))
    overrides.pop("_comment", None)

    if args.repos_file:
        repos = json.loads(Path(args.repos_file).read_text(encoding="utf-8"))
    else:
        repos = fetch_repos()
        if args.save_repos:
            Path(args.save_repos).write_text(json.dumps(repos, ensure_ascii=False, indent=1), encoding="utf-8")

    projects = collect(repos, overrides)
    if not projects:
        sys.exit("No public repositories found; refusing to publish an empty page.")

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(ROOT / "assets", out / "assets")

    template = (ROOT / "templates" / "page.html").read_text(encoding="utf-8")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    for lang in LANGS:
        t = translations[lang]
        is_bg = lang == "bg"
        context = {
            "lang": lang,
            "base": "" if is_bg else "../",
            "url_self": SITE_URL if is_bg else f"{SITE_URL}en/",
            "url_bg": SITE_URL,
            "url_en": f"{SITE_URL}en/",
            "href_bg": "./" if is_bg else "../",
            "href_en": "en/" if is_bg else "./",
            "current_bg": ' aria-current="page"' if is_bg else "",
            "current_en": "" if is_bg else ' aria-current="page"',
            "stats": render_stats(projects, lang, t),
            "projects_featured": "\n\t\t\t\t\t".join(render_card(p, lang, t) for p in projects if p["group"] == "featured"),
            "projects_archive": "\n\t\t\t\t\t".join(render_archive_item(p, lang, t) for p in projects if p["group"] == "archive"),
            "updated": esc(format_date(today, t)),
            "logo_full": inline_svg("logo-full.svg", "brand__logo"),
            "logo_monogram": inline_svg("logo-monogram.svg", "orbit__logo"),
            "updated_iso": today,
        }
        target = out / "index.html" if is_bg else out / "en" / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(template, context, t), encoding="utf-8", newline="\n")

    bg, en = translations["bg"], translations["en"]
    (out / "404.html").write_text(
        NOT_FOUND.format(
            logo=inline_svg("logo-full.svg", "brand__logo brand__logo--large"),
            bg_title=esc(bg["not_found_title"]),
            en_title=esc(en["not_found_title"]),
            bg_text=esc(bg["not_found_text"]),
            en_text=esc(en["not_found_text"]),
            bg_home=esc(bg["not_found_home"]),
            en_home=esc(en["not_found_home"]),
        ),
        encoding="utf-8",
        newline="\n",
    )
    write_moved_pages(out)
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8", newline="\n")
    alternates = "".join(
        f'\n\t\t<xhtml:link rel="alternate" hreflang="{lang}" href="{SITE_URL if lang == "bg" else SITE_URL + "en/"}"/>' for lang in LANGS
    )
    urls = "".join(
        f"\n\t<url>\n\t\t<loc>{loc}</loc>\n\t\t<lastmod>{today}</lastmod>{alternates}\n\t</url>" for loc in (SITE_URL, f"{SITE_URL}en/")
    )
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{urls}\n</urlset>\n',
        encoding="utf-8",
        newline="\n",
    )

    featured = sum(1 for p in projects if p["group"] == "featured")
    print(f"built {out}: {len(projects)} projects ({featured} featured, {len(projects) - featured} archive)")


if __name__ == "__main__":
    main()
