"""图片下载器"""
import asyncio
import aiohttp
import os
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
import requests

from config import load_config


class ImageDownloader:
    """异步图片下载器"""

    def __init__(self, gallery_id: int):
        self.gallery_id = gallery_id
        self.config = load_config()
        self.download_dir = Path(self.config["download_dir"]) / str(gallery_id)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = None

    async def download_images(self, image_urls: List[str], progress_callback=None) -> List[str]:
        """异步下载所有图片

        Args:
            image_urls: 图片 URL 列表
            progress_callback: 进度回调函数 (current, total)

        Returns:
            下载完成的图片路径列表
        """
        proxy = self.config.get("proxy", "socks5://127.0.0.1:10808")

        connector = aiohttp.TCPConnector(limit=3)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            self.session = session
            tasks = []
            for i, url in enumerate(image_urls):
                task = self._download_single(url, i + 1, proxy, progress_callback, len(image_urls))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤失败的，整理顺序
        downloaded = []
        for i, result in enumerate(results):
            if isinstance(result, str) and os.path.exists(result):
                downloaded.append(result)
            else:
                # 尝试同步下载作为后备
                sync_result = self._sync_download(image_urls[i], i + 1)
                if sync_result:
                    downloaded.append(sync_result)

        return sorted(downloaded, key=lambda x: int(Path(x).stem))

    async def _download_single(
        self, url: str, page_num: int, proxy: str,
        progress_callback, total: int
    ) -> Optional[str]:
        """下载单张图片"""
        ext = url.split(".")[-1] if "." in url else "webp"
        filename = f"{page_num}.{ext}"
        filepath = self.download_dir / filename

        # 断点续传：检查已存在的文件
        if filepath.exists() and filepath.stat().st_size > 1000:
            if progress_callback:
                progress_callback(page_num, total)
            return str(filepath)

        try:
            # 构建代理
            proxy_url = proxy if proxy.startswith("socks5") else f"socks5://{proxy}"

            async with self.session.get(url, proxy=proxy_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(filepath, "wb") as f:
                        f.write(content)

                    if progress_callback:
                        progress_callback(page_num, total)

                    return str(filepath)
        except Exception as e:
            print(f"下载失败 {url}: {e}")

        return None

    def _sync_download(self, url: str, page_num: int) -> Optional[str]:
        """同步下载作为后备"""
        ext = url.split(".")[-1] if "." in url else "webp"
        filename = f"{page_num}.{ext}"
        filepath = self.download_dir / filename

        if filepath.exists() and filepath.stat().st_size > 1000:
            return str(filepath)

        try:
            proxies = {
                "http": self.config.get("proxy", "socks5://127.0.0.1:10808"),
                "https": self.config.get("proxy", "socks5://127.0.0.1:10808"),
            }
            resp = requests.get(url, proxies=proxies, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return str(filepath)
        except Exception as e:
            print(f"同步下载失败 {url}: {e}")

        return None

    def get_downloaded_images(self) -> List[str]:
        """获取已下载的图片列表"""
        if not self.download_dir.exists():
            return []

        images = []
        for f in self.download_dir.iterdir():
            if f.suffix.lower() in [".webp", ".jpg", ".jpeg", ".png"]:
                images.append(str(f))

        return sorted(images, key=lambda x: int(Path(x).stem))