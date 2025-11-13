from __future__ import annotations
from urllib.parse import urlparse, urlunparse
import re

_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

def _strip(u: str) -> str:
    return (u or "").strip()

def _is_data_or_empty(u: str) -> bool:
    u = _strip(u)
    return (not u) or u.startswith("data:")

def _ensure_https(u: str) -> str:
    u = _strip(u)
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    return u

def _looks_like_direct_image(u: str) -> bool:
    """是否像是可直接顯示的圖片 URL（副檔名或 geekdo-images 網域）。"""
    u = _strip(u)
    if not u:
        return False
    up = urlparse(u)
    path = up.path.lower()
    if path.endswith(_IMG_EXT):
        return True
    # geekdo CDN 通常為直接圖，即便路徑未帶副檔名也可嘗試
    if up.netloc.endswith("geekdo-images.com") or up.netloc.endswith("cf.geekdo-images.com"):
        return True
    return False

def _is_bgg_image_page(u: str) -> bool:
    """是否為 BGG 的 image 頁面（HTML），不適合前端直接當圖片。"""
    u = _strip(u)
    if not u:
        return False
    up = urlparse(u)
    host = up.netloc.lower()
    path = up.path.lower()
    q = up.query.lower()
    if "boardgamegeek.com" in host:
        if "/image/" in path or "/images/" in path or "__imagepage" in q or "imagepage" in path:
            return True
    return False

def _remove_query(u: str) -> str:
    up = urlparse(u)
    up2 = up._replace(query="")
    return urlunparse(up2)

def normalize_bgg_image_url(raw: str) -> str:
    """
    將各種 BGG 來源的圖片欄位正規化為「可直接顯示」的 URL。
    規則：
    1) 空／data: 一律返回空字串（由上層做 fallback）。
    2) 協定相對 // 轉 https://
    3) 直接圖（有圖檔副檔名或 geekdo-images.com）：返回清理後 URL（去 query）。
    4) 若判定是 BGG 的 image HTML 頁（/image/ 或帶 __imagepage），返回空字串讓上層 fallback。
    """
    u = _ensure_https(raw)
    if _is_data_or_empty(u):
        return ""

    # BGG 的 image HTML 頁面，不回傳，交由上層改用其他來源
    if _is_bgg_image_page(u):
        return ""

    # 直接圖：回傳去 query 後的 URL
    if _looks_like_direct_image(u):
        return _remove_query(u)

    # 其他未知格式：若看起來不是直連圖，返回空字串以便上層 fallback
    return ""
