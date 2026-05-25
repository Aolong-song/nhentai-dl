"""Nhentai Downloader - Web 界面启动器 v2.1 (PyInstaller 兼容)"""
import sys
import os
import threading
import time
from pathlib import Path

def get_html_path():
    """获取 gui_new.html 的正确路径（兼容 PyInstaller）"""
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "gui_new.html"

def start_server():
    import tkinter as tk
    from tkinter import filedialog
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, FileResponse
    import requests
    import urllib3
    import re
    import json
    import config as config_module
    from api_client import NhentaiAPI
    from pdf_builder import PDFBuilder

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    app = FastAPI(title="Nhentai Downloader API", version="2.1")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    api = NhentaiAPI()

    # ─── 任务状态管理 ───
    class DownloadTask:
        def __init__(self, gallery_id):
            self.gallery_id = gallery_id
            self.status = "pending"
            self.progress = 0
            self.current = 0
            self.total = 0
            self.message = "等待中..."
            self.result = None
            self.error = None
            self._lock = threading.Lock()
        def update(self, status=None, progress=None, current=None, total=None, message=None, result=None, error=None):
            with self._lock:
                if status is not None: self.status = status
                if progress is not None: self.progress = progress
                if current is not None: self.current = current
                if total is not None: self.total = total
                if message is not None: self.message = message
                if result is not None: self.result = result
                if error is not None: self.error = error
        def to_dict(self):
            with self._lock:
                return {"gallery_id": self.gallery_id, "status": self.status, "progress": self.progress,
                        "current": self.current, "total": self.total, "message": self.message,
                        "result": self.result, "error": self.error}

    class TaskManager:
        def __init__(self):
            self.tasks = {}
            self._lock = threading.Lock()
        def create_task(self, gid):
            with self._lock: t = DownloadTask(gid); self.tasks[gid] = t; return t
        def get_task(self, gid):
            with self._lock: return self.tasks.get(gid)

    tm = TaskManager()

    def sanitize(name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)[:80]

    def get_title(g):
        return g.get("title", {}).get("english") or g.get("title", {}).get("japanese") or g.get("english_title") or g.get("japanese_title") or "Unknown"

    def parse_gid(text):
        text = text.strip()
        m = re.search(r'nhentai\.net/g/(\d+)', text)
        if m: return int(m.group(1))
        m = re.search(r'/g/(\d+)', text)
        if m: return int(m.group(1))
        if text.isdigit(): return int(text)
        return None

    # ─── 路由 ───
    @app.get("/")
    async def root(): return {"status": "ok", "service": "Nhentai Downloader API v2.1"}

    @app.get("/ui")
    async def ui():
        """托管前端 HTML 页面"""
        html_path = get_html_path()
        if not html_path.exists():
            return {"error": f"HTML file not found: {html_path}"}
        return FileResponse(str(html_path), media_type="text/html")

    @app.get("/gallery/{gallery_id}")
    async def get_gallery(gallery_id: int):
        try: return api.get_gallery(gallery_id)
        except Exception as e: raise HTTPException(status_code=500, detail=str(e))

    @app.post("/search")
    async def search(req: dict):
        try:
            q = req.get("query", "")
            gid = parse_gid(q)
            if gid:
                g = api.get_gallery(gid)
                return {"data": [g], "total": 1}
            else:
                r = api.search(q)
                return {"data": r.get("data", r.get("result", []))[:50], "total": len(r.get("data", []))}
        except Exception as e: raise HTTPException(status_code=500, detail=str(e))

    @app.post("/popular")
    async def popular(req: dict):
        try:
            sort = req.get("sort", "today")
            lang = req.get("language", "all")
            sort_map = {"today": "popular-today", "week": "popular-week", "month": "popular-month"}
            sp = sort_map.get(sort, "popular-today")
            query = {"chinese": "language:chinese", "english": "language:english", "japanese": "language:japanese"}.get(lang, "a")
            r = api._get("/search", params={"query": query, "sort": sp, "page": 1})
            return {"data": r.get("result", []), "total": len(r.get("result", []))}
        except Exception as e: raise HTTPException(status_code=500, detail=str(e))

    @app.post("/download")
    async def start_download(req: dict):
        gid = req.get("gallery_id")
        existing = tm.get_task(gid)
        if existing and existing.status == "downloading":
            return {"task_id": gid, "status": "already_downloading"}
        task = tm.create_task(gid)
        threading.Thread(target=_download, args=(gid,), daemon=True).start()
        return {"task_id": gid, "status": "started"}

    def _download(gallery_id):
        task = tm.get_task(gallery_id)
        if not task: return
        try:
            cfg = config_module.load_config()
            task.update(status="downloading", message=f"获取本子 #{gallery_id}...")

            g = api.get_gallery(gallery_id)
            title = get_title(g)
            pages = g.get("num_pages", 0)
            media_id = g.get("media_id")

            imgs = []
            for p in g.get("pages", []):
                n = p.get("number", 1)
                ext = (p.get("path") or "").split(".")[-1] or "jpg"
                imgs.append(f"https://i.nhentai.net/galleries/{media_id}/{n}.{ext}")

            folder = f"{gallery_id}_{sanitize(title)}"
            ddir = Path(cfg.get("download_dir", config_module.get_default_download_dir()))
            fpath = ddir / folder
            fpath.mkdir(parents=True, exist_ok=True)

            proxy = {"http": cfg.get("proxy","socks5://127.0.0.1:10808"), "https": cfg.get("proxy","socks5://127.0.0.1:10808")}
            downloaded = []
            total = len(imgs)

            for i, url in enumerate(imgs):
                ext = url.split(".")[-1]
                fp = fpath / f"{i+1}.{ext}"
                task.update(current=i+1, total=total, progress=int((i+1)/total*100), message=f"下载 {i+1}/{total}")

                if fp.exists() and fp.stat().st_size >= 1000:
                    downloaded.append(str(fp)); continue
                for attempt in range(3):
                    try:
                        r = requests.get(url, proxies=proxy, timeout=30, headers={"User-Agent":"Mozilla/5.0"}, verify=False)
                        if r.status_code == 200 and len(r.content) >= 1000:
                            with open(fp,"wb") as f: f.write(r.content); break
                    except:
                        if attempt < 2: time.sleep(2)
                else: fp.write_text("FAILED")
                downloaded.append(str(fp))

            valid = [p for p in downloaded if Path(p).exists() and Path(p).stat().st_size >= 1000]
            if len(valid) < len(imgs):
                task.update(status="error", message=f"下载不完整: {len(valid)}/{len(imgs)}"); return

            task.update(message="生成 PDF...")
            pdf_path = fpath / f"{gallery_id}_{sanitize(title)}.pdf"
            if not PDFBuilder.create_pdf(valid, str(pdf_path)):
                task.update(status="error", message="PDF 生成失败"); return

            config_module.add_history(gallery_id, title, str(pdf_path), pages)
            task.update(status="done", progress=100, message="下载完成", result={"pdf_path": str(pdf_path), "pages": pages, "title": title})
        except Exception as e:
            import traceback; traceback.print_exc()
            task.update(status="error", message=f"失败: {str(e)}", error=str(e))

    @app.get("/download/status/{gallery_id}")
    async def status(gallery_id: int):
        t = tm.get_task(gallery_id)
        if not t: return {"gallery_id": gallery_id, "status": "not_found"}
        return t.to_dict()

    @app.get("/download/progress/{gallery_id}")
    async def progress(gallery_id: int):
        async def gen():
            seen_states = set()
            for _ in range(600):
                t = tm.get_task(gallery_id)
                if not t:
                    yield f"data: {json.dumps({'status':'not_found','progress':0})}\n\n"
                    break
                state = t.to_dict()
                state_key = f"{state['status']}|{state['progress']}|{state['current']}"
                if state_key not in seen_states:
                    seen_states.add(state_key)
                    yield f"data: {json.dumps(state)}\n\n"
                    if state['status'] in ("done", "error"):
                        break
                import asyncio
                await asyncio.sleep(0.5)
            yield f"data: {json.dumps({'status':'closed','progress':100})}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/history")
    async def history(): return {"data": config_module.load_history()}

    @app.get("/config")
    async def get_config():
        cfg = config_module.load_config()
        cfg.pop("api_key", None)
        return cfg

    @app.post("/config")
    async def update_config(req: dict):
        current = config_module.load_config()
        if "download_dir" in req: current["download_dir"] = req["download_dir"]
        if "proxy" in req: current["proxy"] = req["proxy"]
        config_module.save_config(current)
        return {"success": True}

    @app.post("/select_folder")
    async def select_folder():
        """通过 tkinter 打开文件夹选择对话框"""
        result = {"path": None}
        import queue as _queue
        q = _queue.Queue()

        def ask():
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                path = filedialog.askdirectory(title="选择下载目录")
                root.destroy()
                result["path"] = path or None
                q.put(("ok", result["path"]))
            except Exception as e:
                q.put(("error", str(e)))

        t = threading.Thread(target=ask)
        t.start()
        t.join(timeout=30)

        if result["path"]:
            cfg = config_module.load_config()
            cfg["download_dir"] = result["path"]
            config_module.save_config(cfg)
            return {"path": result["path"]}
        return {"path": None, "error": "超时或取消"}

    print("API 服务: http://localhost:28473")
    print("界面地址: http://localhost:28473/ui")
    uvicorn.run(app, host="0.0.0.0", port=28473, log_level="warning")

if __name__ == "__main__":
    import webbrowser
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(3)
    webbrowser.open("http://localhost:28473/ui")
    print("已在浏览器打开界面: http://localhost:28473/ui")
    print("按 Ctrl+C 停止服务")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("已停止")