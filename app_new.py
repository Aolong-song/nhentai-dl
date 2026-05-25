"""Nhentai Downloader - FastAPI 后端服务（带进度流）"""
import sys
import os
import json
import re
import time
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent))
from api_client import NhentaiAPI
from pdf_builder import PDFBuilder
import config as config_module

PROXY = {"http": "socks5://127.0.0.1:10808", "https": "socks5://127.0.0.1:10808"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

app = FastAPI(title="Nhentai Downloader API", version="2.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

api = NhentaiAPI()

# ─── 下载任务状态管理 ───
class DownloadTask:
    def __init__(self, gallery_id: int):
        self.gallery_id = gallery_id
        self.status = "pending"  # pending | downloading | done | error
        self.progress = 0
        self.current = 0
        self.total = 0
        self.message = "等待中..."
        self.result = None
        self.error = None
        self._lock = threading.Lock()

    def update(self, status=None, progress=None, current=None, total=None, message=None):
        with self._lock:
            if status is not None: self.status = status
            if progress is not None: self.progress = progress
            if current is not None: self.current = current
            if total is not None: self.total = total
            if message is not None: self.message = message

    def to_dict(self):
        with self._lock:
            return {
                "gallery_id": self.gallery_id,
                "status": self.status,
                "progress": self.progress,
                "current": self.current,
                "total": self.total,
                "message": self.message,
                "result": self.result,
                "error": self.error,
            }

class TaskManager:
    def __init__(self):
        self.tasks: Dict[int, DownloadTask] = {}
        self._lock = threading.Lock()
        self._subscribers: List[queue.Queue] = []
        self._sub_lock = threading.Lock()

    def create_task(self, gallery_id: int) -> DownloadTask:
        with self._lock:
            task = DownloadTask(gallery_id)
            self.tasks[gallery_id] = task
            return task

    def get_task(self, gallery_id: int) -> Optional[DownloadTask]:
        with self._lock:
            return self.tasks.get(gallery_id)

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast(self, task: DownloadTask):
        data = task.to_dict()
        with self._sub_lock:
            for q in self._subscribers[:]:
                try:
                    q.put_nowait(data)
                except:
                    pass

task_manager = TaskManager()

# ─── 模型 ───
class SearchRequest(BaseModel):
    query: str

class PopularRequest(BaseModel):
    sort: str = "today"
    language: str = "all"

class DownloadRequest(BaseModel):
    gallery_id: int

class ConfigRequest(BaseModel):
    download_dir: Optional[str] = None
    proxy: Optional[str] = None

# ─── 辅助函数 ───
def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:80]

def get_title(g: Dict) -> str:
    return (g.get("title", {}).get("english")
            or g.get("title", {}).get("japanese")
            or g.get("english_title")
            or g.get("japanese_title")
            or "Unknown")

def load_config() -> Dict:
    return config_module.load_config()

def parse_input_to_gallery_id(text: str):
    text = text.strip()
    m = re.search(r'nhentai\.net/g/(\d+)', text)
    if m: return int(m.group(1))
    m = re.search(r'/g/(\d+)', text)
    if m: return int(m.group(1))
    if text.isdigit(): return int(text)
    return None

# ─── 路由 ───
@app.get("/")
async def root():
    return {"status": "ok", "service": "Nhentai Downloader API v2.1", "version": "2.1"}

@app.get("/gallery/{gallery_id}")
async def get_gallery(gallery_id: int):
    try:
        gallery = api.get_gallery(gallery_id)
        return gallery
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_galleries(req: SearchRequest):
    try:
        gid = parse_input_to_gallery_id(req.query)
        if gid:
            gallery = api.get_gallery(gid)
            return {"data": [gallery], "total": 1}
        else:
            result = api.search(req.query)
            galleries = result.get("data", result.get("result", []))
            return {"data": galleries[:50], "total": len(galleries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/popular")
async def get_popular(req: PopularRequest):
    try:
        sort_map = {"today": "popular-today", "week": "popular-week", "month": "popular-month"}
        sort_param = sort_map.get(req.sort, "popular-today")

        if req.language == "chinese": query = "language:chinese"
        elif req.language == "english": query = "language:english"
        elif req.language == "japanese": query = "language:japanese"
        else: query = "a"

        result = api._get("/search", params={"query": query, "sort": sort_param, "page": 1})
        galleries = result.get("result", [])
        return {"data": galleries, "total": len(galleries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download")
async def start_download(req: DownloadRequest):
    """立即返回任务 ID，实际下载在后台进行"""
    gallery_id = req.gallery_id

    # 检查是否已有在进行中的任务
    existing = task_manager.get_task(gallery_id)
    if existing and existing.status == "downloading":
        return {"task_id": gallery_id, "status": "already_downloading"}

    task = task_manager.create_task(gallery_id)

    # 后台线程执行下载
    thread = threading.Thread(target=_download_worker, args=(gallery_id,), daemon=True)
    thread.start()

    return {"task_id": gallery_id, "status": "started"}

def _download_worker(gallery_id: int):
    """后台下载 worker"""
    task = task_manager.get_task(gallery_id)
    if not task:
        return

    try:
        cfg = load_config()
        task.update(status="downloading", message=f"获取本子 #{gallery_id}...")

        gallery = api.get_gallery(gallery_id)
        title = get_title(gallery)
        pages = gallery.get("num_pages", 0)
        media_id = gallery.get("media_id")

        task.update(message=f"正在下载: {title[:30]}...")
        task_manager.broadcast(task)

        # 构建图片 URL
        image_urls = []
        for p in gallery.get("pages", []):
            num = p.get("number", 1)
            path = p.get("path", "")
            ext = path.split(".")[-1] if "." in path else "jpg"
            image_urls.append(f"https://i.nhentai.net/galleries/{media_id}/{num}.{ext}")

        # 下载目录
        folder_name = f"{gallery_id}_{sanitize_folder_name(title)}"
        download_dir = Path(cfg.get("download_dir", config_module.get_default_download_dir()))
        folder_path = download_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        proxy_cfg = {
            "http": cfg.get("proxy", "socks5://127.0.0.1:10808"),
            "https": cfg.get("proxy", "socks5://127.0.0.1:10808"),
        }

        downloaded = []
        total = len(image_urls)

        for i, url in enumerate(image_urls):
            ext = url.split(".")[-1]
            filepath = folder_path / f"{i+1}.{ext}"

            task.update(current=i+1, total=total, progress=int((i+1)/total*100),
                        message=f"下载图片 {i+1}/{total}")
            task_manager.broadcast(task)

            # 跳过已下载
            if filepath.exists() and filepath.stat().st_size >= 1000:
                downloaded.append(str(filepath))
                continue

            # 下载（3次重试）
            for attempt in range(3):
                try:
                    resp = requests.get(url, proxies=proxy_cfg, timeout=30,
                                        headers=HEADERS, verify=False)
                    if resp.status_code == 200 and len(resp.content) >= 1000:
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        break
                except:
                    if attempt < 2:
                        time.sleep(2)
            else:
                filepath.write_text("FAILED")

            downloaded.append(str(filepath))

        # 检查完整性
        valid = [p for p in downloaded if Path(p).exists() and Path(p).stat().st_size >= 1000]
        task.update(message=f"验证图片: {len(valid)}/{total} 有效")
        task_manager.broadcast(task)

        if len(valid) < len(image_urls):
            task.update(status="error", message=f"下载不完整: {len(valid)}/{len(image_urls)}")
            task_manager.broadcast(task)
            return

        # 生成 PDF
        task.update(message="生成 PDF...")
        task_manager.broadcast(task)

        pdf_name = f"{gallery_id}_{sanitize_folder_name(title)}.pdf"
        pdf_path = folder_path / pdf_name

        success = PDFBuilder.create_pdf(valid, str(pdf_path))

        if not success:
            task.update(status="error", message="PDF 生成失败")
            task_manager.broadcast(task)
            return

        # 保存历史
        config_module.add_history(gallery_id, title, str(pdf_path), pages)

        task.update(status="done", progress=100, message="下载完成",
                    result={"pdf_path": str(pdf_path), "pages": pages, "title": title})
        task_manager.broadcast(task)

    except Exception as e:
        import traceback
        task.update(status="error", message=f"下载失败: {str(e)}", error=str(e))
        task_manager.broadcast(task)

@app.get("/download/status/{gallery_id}")
async def get_download_status(gallery_id: int):
    """获取下载任务状态"""
    task = task_manager.get_task(gallery_id)
    if not task:
        return {"gallery_id": gallery_id, "status": "not_found"}
    return task.to_dict()

@app.get("/download/progress/{gallery_id}")
async def progress_stream(gallery_id: int):
    """SSE 流式进度推送"""
    async def event_generator():
        task = task_manager.get_task(gallery_id)
        last_state = ""
        while True:
            task = task_manager.get_task(gallery_id)
            if not task:
                break
            state = f"{task.status}|{task.progress}|{task.current}|{task.total}|{task.message}"
            if state != last_state:
                last_state = state
                data = json.dumps(task.to_dict())
                yield f"data: {data}\n\n"
                if task.status in ("done", "error"):
                    break
            time.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/history")
async def get_history():
    try:
        history = config_module.load_history()
        return {"data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config():
    try:
        cfg = load_config()
        cfg.pop("api_key", None)
        return cfg
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/config")
async def update_config(req: ConfigRequest):
    try:
        current = load_config()
        if req.download_dir is not None:
            current["download_dir"] = req.download_dir
        if req.proxy is not None:
            current["proxy"] = req.proxy
        config_module.save_config(current)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("启动 API 服务: http://localhost:28473")
    uvicorn.run(app, host="0.0.0.0", port=28473, log_level="warning")