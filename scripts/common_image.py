# scripts/common_image.py
from __future__ import annotations
import re

def normalize_bgg_image_url(cand: str | None) -> str | None:
    """
    將 BGG 來源的 image/thumbnail 或含 __imagepage 的 URL，轉為可直接顯示的圖檔連結。
    不保證補圖，只做「可用就回傳、不可用回 None」。
    """
    if not cand:
        return None
    u = str(cand).strip()
    if not u or u.lower() == "n/a":
        return None

    # 統一 https
    u = u.replace("http://", "https://")

    # 移除 __imagepage 標記/尾巴
    u = re.sub(r'__imagepage(?:\?.*)?$', '', u, flags=re.IGNORECASE)

    # 直接接受常見圖檔副檔名
    if re.search(r'\.(jpg|jpeg|png|webp)(?:\?.*)?$', u, flags=re.IGNORECASE):
        return u

    # BGG/Geekdo CDN（有時沒有副檔名也能直連）
    if re.match(r'^https://(cf\.geekdo-images\.com|images\.boardgamegeek\.com)/', u):
        return u

    # 明確是 image 頁面而非檔案，視為無效
    if re.search(r'/image/\d+/?$', u):
        return None

    # 其他未知型態，保守不回傳
    return None
