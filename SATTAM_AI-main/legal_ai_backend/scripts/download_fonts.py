"""
scripts/download_fonts.py

Downloads Noto Sans fonts needed for multilingual PDF export.
Run once: python scripts/download_fonts.py

Noto fonts support Tamil, Hindi, Telugu, Malayalam, Kannada + Latin.
Total download size: ~4MB
"""

import os
import urllib.request

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

# Google Fonts CDN — direct TTF download links
FONTS = {
    "NotoSans-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/"
        "NotoSans-Regular.ttf"
    ),
    "NotoSans-Bold.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/"
        "NotoSans-Bold.ttf"
    ),
    "NotoSansTamil-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTamil/"
        "NotoSansTamil-Regular.ttf"
    ),
    "NotoSansDevanagari-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansDevanagari/"
        "NotoSansDevanagari-Regular.ttf"
    ),
    "NotoSansTelugu-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTelugu/"
        "NotoSansTelugu-Regular.ttf"
    ),
    "NotoSansMalayalam-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansMalayalam/"
        "NotoSansMalayalam-Regular.ttf"
    ),
    "NotoSansKannada-Regular.ttf": (
        "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansKannada/"
        "NotoSansKannada-Regular.ttf"
    ),
}


def download_fonts():
    print(f"Downloading fonts to: {FONTS_DIR}\n")
    for filename, url in FONTS.items():
        dest = os.path.join(FONTS_DIR, filename)
        if os.path.exists(dest):
            print(f"  ✓ Already exists: {filename}")
            continue
        print(f"  Downloading: {filename} ...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            size_kb = os.path.getsize(dest) // 1024
            print(f"done ({size_kb}KB)")
        except Exception as e:
            print(f"FAILED — {e}")
            print(f"    Manual download: {url}")

    print(f"\nDone. Fonts saved to: {FONTS_DIR}")
    print("Restart your backend server after downloading fonts.")


if __name__ == "__main__":
    download_fonts()