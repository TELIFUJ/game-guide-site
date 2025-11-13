# scripts/common_image.py
from __future__ import annotations

def normalize_bgg_image_url(url: str | None) -> str | None:
    """把 BGG 的 __imagepage 轉成可直接顯示的圖片 URL，順便把過大的 fit-in 降到 400x300。"""
    if not url:
        return None
    u = url
    if "__imagepage" in u:
        u = u.replace("__imagepage", "__small@2x")
    # 常見模板把大圖裁成 900x600；前端卡片用 400x300 足夠
    if "/fit-in/900x600/" in u:
        u = u.replace("/fit-in/900x600/", "/fit-in/400x300/")
    return u
