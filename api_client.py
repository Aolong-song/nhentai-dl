"""Nhentai API 客户端"""
import os
import requests
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

# 从环境变量读取配置（敏感信息不应硬编码）
API_KEY = os.environ.get('NHENTAI_API_KEY', '')
PROXY = os.environ.get('HTTP_PROXY', '') or os.environ.get('HTTPS_PROXY', '')

# 验证配置
if not API_KEY:
    raise ValueError(
        "NHENTAI_API_KEY 环境变量未设置。\n"
        "请访问 https://nhentai.net/settings/ 获取 API Key，"
        "并通过以下方式配置：\n"
        "  Linux/Mac: export NHENTAI_API_KEY='nhk_xxx'\n"
        "  Windows:   set NHENTAI_API_KEY=nhk_xxx\n"
        "  或复制 .env.example 为 .env 并填入配置"
    )

BASE_URL = "https://nhentai.net/api/v2"
PROXY_DICT = {"http": PROXY, "https": PROXY} if PROXY else {}
HEADERS = {
    "Authorization": f"Key {API_KEY}",
    "User-Agent": "NhentaiDownloader/1.0",
    "Accept": "application/json",
}


class NhentaiAPI:
    """nhentai.net API 客户端"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if PROXY_DICT:
            self.session.proxies = PROXY_DICT

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """GET 请求"""
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_gallery(self, gallery_id: int) -> Dict:
        """获取本子详情"""
        return self._get(f"/galleries/{gallery_id}")

    def search(
        self,
        query: str,
        sort: str = "popular",
        page: int = 1,
        language: str = "chinese",
    ) -> Dict:
        """搜索本子"""
        params = {
            "query": query,
            "sort": sort,
            "page": page,
        }
        result = self._get("/search", params)

        # API 返回 result 数组（不是 data）
        galleries = result.get("result", [])

        # 语言过滤：只对完整对象进行过滤（单个 gallery 查询有完整 tags）
        if language and language != "all":
            # 搜索结果没有完整 tags，只能粗筛标题中含 [Chinese] 的
            if language == "chinese":
                galleries = [g for g in galleries if "[Chinese]" in g.get("english_title", "") or "[Chinese]" in g.get("japanese_title", "")]

        result["data"] = galleries
        return result

    def _has_language(self, gallery: Dict, language: str) -> bool:
        """检查本子是否包含指定语言标签"""
        for tag in gallery.get("tags", []):
            if tag.get("type") == "language" and language in tag.get("name", "").lower():
                return True
        return False

    def get_popular(self, sort: str = "today") -> Dict:
        """获取热门榜单

        sort: today, week, month
        """
        sort_map = {"today": "popular-today", "week": "popular-week", "month": "popular-month"}
        sort_param = sort_map.get(sort, "popular-today")

        result = self._get("/search", params={"query": "a", "sort": sort_param, "page": 1})
        # API 返回 result 数组（不是 data），结果本身就按 popular 排序
        result["data"] = result.get("result", [])
        return result

    def get_tags(self, tag_type: str) -> List[Dict]:
        """获取标签列表

        tag_type: category, language, tag, character, artist, group, parody
        """
        return self._get("/tags", params={"type": tag_type})

    def get_gallery_images(self, gallery: Dict) -> List[str]:
        """获取本子所有图片的 URL 列表"""
        media_id = gallery.get("media_id")
        pages = gallery.get("pages", [])

        image_urls = []
        for page in pages:
            page_num = page.get("number", 1)
            # 尝试 webp 格式
            path = page.get("path", "")
            if path:
                ext = path.split(".")[-1] if "." in path else "webp"
                url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
                image_urls.append(url)

        return image_urls

    def get_cover_url(self, gallery: Dict) -> str:
        """获取封面 URL"""
        media_id = gallery.get("media_id")
        cover = gallery.get("cover", {})
        path = cover.get("path", "")
        ext = path.split(".")[-1] if "." in path else "webp"
        return f"https://i.nhentai.net/galleries/{media_id}/cover.{ext}"

    def get_thumbnail_url(self, gallery: Dict) -> str:
        """获取缩略图 URL"""
        media_id = gallery.get("media_id")
        thumb = gallery.get("thumbnail", {})
        path = thumb.get("path", "")
        ext = path.split(".")[-1] if "." in path else "webp"
        return f"https://t.nhentai.net/galleries/{media_id}/thumb.{ext}"