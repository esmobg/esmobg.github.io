#!/usr/bin/env python3
"""Make a project preview image for a card: 800x500 WebP (16:10, made for 2x screens).

Usage:
    python tools/screenshot.py https://example.com/ assets/img/projects/example.webp
    python tools/screenshot.py path/to/screenshot.png assets/img/projects/example.webp

A URL is captured with headless Google Chrome or Chromium at 1280x800. A local image is
cropped to 16:10 from the top centre (the top of a page is the part worth showing).

Needs Pillow (pip install pillow) and, for URLs, Chrome or Chromium. The daily site build
does not run this: preview images are committed to the repository, and build.py only reads
their size. Projects without a preview image get a generated cover instead.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

WIDTH, HEIGHT = 800, 500
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def capture(url: str, target: Path) -> None:
    browser = next((b for b in BROWSERS if shutil.which(b)), None)
    if not browser:
        sys.exit("Chrome or Chromium is needed to capture a URL.")
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--window-size=1280,800",
            "--virtual-time-budget=8000",
            f"--screenshot={target}",
            url,
        ],
        check=True,
        timeout=120,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def preview(source: Path, target: Path) -> None:
    image = Image.open(source).convert("RGB")
    ratio = WIDTH / HEIGHT
    if image.width / image.height > ratio:
        width = round(image.height * ratio)
        left = (image.width - width) // 2
        image = image.crop((left, 0, left + width, image.height))
    else:
        image = image.crop((0, 0, image.width, round(image.width / ratio)))
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=82, method=6)
    print(f"{target}: {WIDTH}x{HEIGHT}, {target.stat().st_size // 1024} KB")


def main() -> None:
    if len(sys.argv) != 3 or not sys.argv[2].endswith(".webp"):
        sys.exit(__doc__)
    source, target = sys.argv[1], Path(sys.argv[2])
    if source.startswith(("http://", "https://")):
        with tempfile.TemporaryDirectory() as tmp:
            shot = Path(tmp) / "shot.png"
            capture(source, shot)
            preview(shot, target)
    else:
        preview(Path(source), target)


if __name__ == "__main__":
    main()
