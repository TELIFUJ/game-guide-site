from __future__ import annotations
from urllib.parse import urlparse, urlunparse

IMG_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif")

def _force_https(u: str) -> str:
    if not u: return ""
    u = u.strip()
    if u.startswith("//"): return "https:" + u
    if u.startswith("http://"): return "https://" + u[7:]
    return u

def _strip_query(u: str) -> str:
    try:
        p = urlparse(u)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return u

def normalize_bgg_image_url(url: str | None) -> str:
    if not url: return ""
    u = _strip_query(_force_https(url))
    lo = u.lower()

    if "geekdo-images.com" in lo:
        if "__imagepage" in u: u = u.replace("__imagepage", "__original")
        if "/imagepage/" in u: u = u.replace("/imagepage/", "/original/")
        return u

    if "boardgamegeek.com/image/" in lo:
        # 這是 HTML 頁面，不能當圖
        return ""

    return u
