"""配置和历史记录管理"""
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# ─── 持久化路径（PyInstaller 兼容） ───
if getattr(sys, 'frozen', False):
    # EXE 运行时：配置写到用户目录，确保持久化
    USER_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'NhentaiDownloader'
    USER_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR = USER_DIR
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "download_history.json"


def get_default_download_dir() -> str:
    """获取默认下载目录"""
    return str(BASE_DIR / "downloads")


def load_config() -> Dict:
    """加载配置"""
    proxy = os.environ.get('HTTP_PROXY', '') or os.environ.get('HTTPS_PROXY', '')

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if proxy:
                    config['proxy'] = proxy
                return config
        except (json.JSONDecodeError, IOError):
            pass

    return {
        "download_dir": get_default_download_dir(),
        "proxy": proxy or "socks5://127.0.0.1:10808",
        "language_filter": "chinese",
    }


def save_config(config: Dict) -> None:
    """保存配置"""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_history() -> List[Dict]:
    """加载下载历史"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def add_history(gallery_id: int, title: str, pdf_path: str, pages: int) -> None:
    """添加下载历史"""
    history = load_history()
    now = datetime.now().isoformat()

    for item in history:
        if item["gallery_id"] == gallery_id:
            item["download_date"] = now
            item["pdf_path"] = pdf_path
            break
    else:
        history.insert(0, {
            "gallery_id": gallery_id,
            "title": title,
            "download_date": now,
            "pdf_path": pdf_path,
            "pages": pages,
        })

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_history_by_gallery(gallery_id: int) -> Optional[Dict]:
    """根据 gallery_id 获取历史记录"""
    history = load_history()
    for item in history:
        if item["gallery_id"] == gallery_id:
            return item
    return None