"""Nhentai Downloader - Tkinter GUI 版本"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import json
import re
import time
import warnings
from pathlib import Path
from datetime import datetime
import requests
import urllib3
from PIL import Image, ImageTk
import io

# 抑制 InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ===================== 常量 & 配色 =====================
BG_DARK = "#1e1e2e"
BG_MID  = "#2a2a3e"
BG_LIGHT= "#363652"
FG_MAIN = "#cdd6f4"
FG_MUTED= "#6c7086"
ACCENT  = "#89b4fa"
ACCENT2 = "#f38ba8"
BTN_BG  = "#313244"
BTN_HV  = "#45475a"

PROXY = {"http": "socks5://127.0.0.1:10808", "https": "socks5://127.0.0.1:10808"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ===================== 工具函数 =====================
def sanitize_folder_name(name: str) -> str:
    """移除文件夹非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:80]

def parse_input_to_gallery_id(text: str):
    """解析用户输入，返回 gallery_id 或 None

    支持格式:
      - 纯数字: 177013
      - nhentai 链接: https://nhentai.net/g/177013/
      - /g/177013/
    """
    text = text.strip()
    m = re.search(r'nhentai\.net/g/(\d+)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'/g/(\d+)', text)
    if m:
        return int(m.group(1))
    if text.isdigit():
        return int(text)
    return None

# ===================== API 客户端 =====================
class NhentaiAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.proxies = PROXY
        self.session.timeout = 30

    def _get(self, path, params=None):
        url = f"https://nhentai.net/api/v2{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_gallery(self, gallery_id):
        return self._get(f"/galleries/{gallery_id}")

    def search(self, query, sort="popular", page=1):
        """搜索（返回 result 数组，简化对象无完整 tags）"""
        params = {"query": query, "sort": sort, "page": page}
        result = self._get("/search", params)
        result["data"] = result.get("result", [])
        return result

    def get_popular(self, sort="today", language="all"):
        sort_map = {"today": "popular-today", "week": "popular-week", "month": "popular-month"}
        sort_param = sort_map.get(sort, "popular-today")

        # nhentai 支持 tag 查询，language:chinese 即搜索中文标签
        if language == "chinese":
            query = "language:chinese"
        elif language == "english":
            query = "language:english"
        elif language == "japanese":
            query = "language:japanese"
        else:
            query = "a"

        result = self._get("/search", params={"query": query, "sort": sort_param, "page": 1})
        result["data"] = result.get("result", [])
        return result

    def get_gallery_images(self, gallery):
        media_id = gallery.get("media_id")
        pages = gallery.get("pages", [])
        image_urls = []
        for page in pages:
            page_num = page.get("number", 1)
            path = page.get("path", "")
            ext = path.split(".")[-1] if "." in path else "webp"
            url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
            image_urls.append(url)
        return image_urls

    def get_thumbnail_url(self, gallery):
        media_id = gallery.get("media_id")
        thumb = gallery.get("thumbnail", {})
        path = thumb.get("path", "")
        ext = path.split(".")[-1] if "." in path else "webp"
        return f"https://t.nhentai.net/galleries/{media_id}/thumb.{ext}"

    def get_cover_url(self, gallery):
        media_id = gallery.get("media_id")
        cover = gallery.get("cover", {})
        path = cover.get("path", "")
        ext = path.split(".")[-1] if "." in path else "webp"
        return f"https://i.nhentai.net/galleries/{media_id}/cover.{ext}"


# ===================== 配置管理 =====================
import sys, os

# EXE 运行时配置写到用户目录，避免临时目录丢失
if getattr(sys, 'frozen', False):
    USER_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'NhentaiDownloader'
    USER_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR = USER_DIR
else:
    BASE_DIR = Path(__file__).parent

CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "download_history.json"

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"download_dir": str(BASE_DIR / "downloads"), "proxy": "socks5://127.0.0.1:10808"}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def add_history(gallery_id, title, pdf_path, pages):
    history = load_history()
    for item in history:
        if item["gallery_id"] == gallery_id:
            item.update({"download_date": datetime.now().isoformat(), "pdf_path": pdf_path})
            break
    else:
        history.insert(0, {"gallery_id": gallery_id, "title": title,
                            "download_date": datetime.now().isoformat(),
                            "pdf_path": pdf_path, "pages": pages})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ===================== PDF 生成 =====================
class PDFBuilder:
    @staticmethod
    def create_pdf(image_paths, output_path):
        if not image_paths:
            return False
        images = []
        for img_path in sorted(image_paths, key=lambda x: int(Path(x).stem or "0")):
            try:
                img = Image.open(img_path)
                if img.mode in ("RGBA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = bg
                images.append(img)
            except Exception as e:
                print(f"处理图片失败 {img_path}: {e}")
                continue
        if not images:
            return False
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            images[0].save(output_path, "PDF", resolution=100.0,
                           save_all=True, append_images=images[1:])
            return True
        except Exception as e:
            print(f"生成 PDF 失败: {e}")
            return False


# ===================== 图片下载 =====================
class ImageDownloader:
    def __init__(self, gallery_id, folder_path: Path, config):
        self.gallery_id = gallery_id
        self.folder_path = folder_path
        self.folder_path.mkdir(parents=True, exist_ok=True)
        self.config = config

    def download_sync(self, image_urls, progress_callback=None):
        proxies = {
            "http":  self.config.get("proxy", "socks5://127.0.0.1:10808"),
            "https": self.config.get("proxy", "socks5://127.0.0.1:10808"),
        }
        downloaded = []
        for i, url in enumerate(image_urls):
            ext = url.split(".")[-1] if "." in url else "webp"
            filepath = self.folder_path / f"{i+1}.{ext}"

            # 文件存在且大小正常 → 跳过
            if filepath.exists() and filepath.stat().st_size >= 1000:
                downloaded.append(str(filepath))
                if progress_callback:
                    progress_callback(i + 1, len(image_urls))
                continue

            # 带重试下载（最多 3 次，失败等 2 秒）
            for attempt in range(3):
                try:
                    resp = requests.get(url, proxies=proxies, timeout=30,
                                        headers=HEADERS, verify=False)
                    if resp.status_code == 200 and len(resp.content) >= 1000:
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        break
                except Exception as e:
                    if attempt == 2:
                        print(f"下载失败 {url}: {e}")
                    else:
                        time.sleep(2)
            else:
                # 3 次全失败，写入占位
                filepath.write_text("FAILED")

            downloaded.append(str(filepath))
            if progress_callback:
                progress_callback(i + 1, len(image_urls))

        return sorted(downloaded, key=lambda x: int(Path(x).stem or "0"))


# ===================== 主应用 =====================
class NhentaiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Nhentai Downloader")
        self.root.geometry("1000x720")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)

        self.api = NhentaiAPI()
        self.config = load_config()
        self.current_results = []       # 当前搜索/榜单结果（简化对象）
        self.current_gallery_full = {} # 当前预览的完整 gallery 信息
        self.download_queue = queue.Queue()
        self.log_queue = queue.Queue()

        self._apply_style()
        self._build_ui()
        self._start_worker()

    # ── 样式 ──────────────────────────────────────────────
    def _apply_style(self):
        style = ttk.Style(self.root)
        self.root.option_add("*Font", ("Microsoft YaHei UI", 9))
        style.theme_use("clam")

        style.configure("TFrame", background=BG_DARK)
        style.configure("DarkFrame", background=BG_DARK)
        style.configure("MidFrame",  background=BG_MID)
        style.configure("LightFrame",background=BG_LIGHT)

        style.configure("TLabel",    background=BG_DARK, foreground=FG_MAIN)
        style.configure("TitleLabel",background=BG_DARK, foreground=ACCENT,
                        font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("MutLabel",  background=BG_DARK, foreground=FG_MUTED)

        style.configure("TButton",   background=BTN_BG, foreground=FG_MAIN,
                        borderwidth=0, padding=(8, 4))
        style.map("TButton",
            background=[("active", BTN_HV), ("pressed", BG_LIGHT)],
            foreground=[("active", FG_MAIN)]
        )
        style.configure("Accent.TButton", background=ACCENT, foreground=BG_DARK,
                        font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Accent.TButton",
            background=[("active", "#a6d8ff"), ("pressed", BG_LIGHT)]
        )

        style.configure("TRadiobutton", background=BG_DARK, foreground=FG_MAIN,
                        borderwidth=0)
        style.map("TRadiobutton",
            background=[("active", BG_DARK)]
        )

        style.configure("TEntry",    fieldbackground=BG_MID, foreground=FG_MAIN,
                        borderwidth=0, insertcolor=FG_MAIN)
        style.configure("TCombobox", fieldbackground=BG_MID, foreground=FG_MAIN,
                        borderwidth=0, arrowcolor=ACCENT)
        style.map("TCombobox", fieldbackground=[("readonly", BG_MID)])

        style.configure("Horizontal.TProgressbar",
            background=ACCENT, troughcolor=BG_MID, borderwidth=0)

    # ── UI 布局 ──────────────────────────────────────────
    def _build_ui(self):
        # ===== 顶部标题栏 =====
        title_bar = tk.Frame(self.root, bg=BG_DARK, pady=8, padx=12)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="📚 Nhentai Downloader",
                 bg=BG_DARK, fg=ACCENT, font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")

        # ===== 搜索栏 =====
        search_bar = tk.Frame(self.root, bg=BG_MID, padx=12, pady=10)
        search_bar.pack(fill="x")

        # 输入框
        tk.Label(search_bar, text="🔍", bg=BG_MID, fg=FG_MAIN).pack(side="left")
        self.search_var = tk.StringVar()
        entry = tk.Entry(search_bar, textvariable=self.search_var,
                          bg=BG_LIGHT, fg=FG_MAIN, insertbackground=FG_MAIN,
                          font=("Consolas", 11), bd=0, relief="flat",
                          width=40)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<Return>", lambda e: self._do_search())
        entry.bind("<Control-a>", lambda e: entry.select_range(0, "end"))

        ttk.Button(search_bar, text="搜索", command=self._do_search,
                   style="Accent.TButton").pack(side="left", padx=3)
        ttk.Button(search_bar, text="随机", command=self._do_random).pack(side="left", padx=3)

        tk.Frame(search_bar, bg=BG_LIGHT, width=1, height=22).pack(side="left", padx=10)

        # 榜单选择
        tk.Label(search_bar, text="📊 榜单", bg=BG_MID, fg=FG_MAIN).pack(side="left")
        self.sort_var = tk.StringVar(value="today")
        for val, lbl in [("today","日"), ("week","周"), ("month","月")]:
            ttk.Radiobutton(search_bar, text=lbl, variable=self.sort_var,
                             value=val).pack(side="left", padx=2)
        ttk.Button(search_bar, text="查看榜单", command=self._do_popular).pack(side="left", padx=(5, 0))

        tk.Frame(search_bar, bg=BG_LIGHT, width=1, height=22).pack(side="left", padx=10)

        # 语言
        tk.Label(search_bar, text="🌐", bg=BG_MID, fg=FG_MAIN).pack(side="left")
        self.lang_var = tk.StringVar(value="chinese")
        lang_combo = ttk.Combobox(search_bar, textvariable=self.lang_var,
                                   values=["chinese", "english", "japanese", "all"],
                                   state="readonly", width=9)
        lang_combo.pack(side="left", padx=4)

        # ===== 主区域（三栏） =====
        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=10, pady=(6, 0))

        # 左：列表
        left = tk.Frame(main, bg=BG_DARK)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="搜索结果", bg=BG_DARK, fg=FG_MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0,4))

        list_frame = tk.Frame(left, bg=BG_MID, bd=0)
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, bg=BG_LIGHT, troughcolor=BG_MID,
                                  width=8, activebackground=ACCENT)
        self.results_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                       bg=BG_MID, fg=FG_MAIN,
                                       font=("Consolas", 9),
                                       highlightthickness=0, bd=0,
                                       selectbackground=BG_LIGHT,
                                       selectforeground=ACCENT)
        scrollbar.config(command=self.results_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.results_list.pack(side="left", fill="both", expand=True)
        self.results_list.bind("<Double-Button-1>", self._on_result_double_click)
        self.results_list.bind("<<ListboxSelect>>", self._on_result_select)

        # 中：预览
        mid = tk.Frame(main, bg=BG_DARK, width=240)
        mid.pack(side="left", fill="y", padx=(6, 0))
        mid.pack_propagate(False)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(1, weight=1)

        tk.Label(mid, text="预览", bg=BG_DARK, fg=FG_MUTED,
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.preview_label = tk.Label(mid, text="(选择本子查看预览)",
                                       bg=BG_MID, fg=FG_MUTED,
                                       font=("Microsoft YaHei UI", 8),
                                       width=24, height=10, anchor="center", justify="center")
        self.preview_label.grid(row=0, column=0, sticky="n", pady=(18, 0))

        self.info_text = scrolledtext.ScrolledText(mid, width=28, height=16,
                                                    bg=BG_MID, fg=FG_MAIN,
                                                    font=("Consolas", 8),
                                                    bd=0, relief="flat",
                                                    insertbackground=FG_MAIN)
        self.info_text.configure(state="disabled")
        self.info_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        btn_row = tk.Frame(mid, bg=BG_DARK)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(btn_row, text="⬇ 下载", command=self._download_selected,
                   style="Accent.TButton").pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(btn_row, text="🔄 重试", command=self._download_selected).pack(
            side="left", expand=True, fill="x")

        # 右：历史记录
        right = tk.Frame(main, bg=BG_DARK, width=200)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)

        tk.Label(right, text="📜 下载历史", bg=BG_DARK, fg=FG_MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0,4))

        hist_frame = tk.Frame(right, bg=BG_MID)
        hist_frame.pack(fill="both", expand=True)
        hist_scroll = tk.Scrollbar(hist_frame, bg=BG_LIGHT, width=6)
        self.history_list = tk.Listbox(hist_frame, yscrollcommand=hist_scroll.set,
                                        bg=BG_MID, fg=FG_MAIN,
                                        font=("Consolas", 8),
                                        highlightthickness=0, bd=0,
                                        selectbackground=BG_LIGHT)
        hist_scroll.config(command=self.history_list.yview)
        hist_scroll.pack(side="right", fill="y")
        self.history_list.pack(side="left", fill="both", expand=True)
        self._refresh_history()

        # 下载目录
        dir_bar = tk.Frame(self.root, bg=BG_MID, padx=12, pady=6)
        dir_bar.pack(fill="x", pady=(6, 0))
        tk.Label(dir_bar, text="📁 下载目录", bg=BG_MID, fg=FG_MUTED).pack(side="left")
        self.dir_var = tk.StringVar(value=self.config.get("download_dir", ""))
        tk.Entry(dir_bar, textvariable=self.dir_var, bg=BG_LIGHT, fg=FG_MAIN,
                  insertbackground=FG_MAIN, font=("Consolas", 9),
                  bd=0, relief="flat", width=55).pack(side="left", padx=8)
        ttk.Button(dir_bar, text="浏览", command=self._browse_dir).pack(side="left", padx=3)
        ttk.Button(dir_bar, text="保存", command=self._save_config).pack(side="left")

        # 进度条
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_bar = ttk.Progressbar(self.root, variable=self.prog_var,
                                        maximum=100,
                                        style="Horizontal.TProgressbar")
        self.prog_bar.pack(fill="x", padx=12, pady=(4, 0))

        # 日志
        log_bar = tk.Frame(self.root, bg=BG_DARK, padx=12, pady=4)
        log_bar.pack(fill="both", expand=True, pady=(4, 0))
        tk.Label(log_bar, text="📋 日志", bg=BG_DARK, fg=FG_MUTED).pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(log_bar, height=5,
                                                    bg=BG_MID, fg=FG_MAIN,
                                                    font=("Consolas", 8),
                                                    bd=0, relief="flat",
                                                    insertbackground=FG_MAIN)
        self.log_text.configure(state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # ── 后台线程 ─────────────────────────────────────────
    def _start_worker(self):
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        self.root.after(100, self._process_queue)

    def _worker(self):
        while True:
            task = self.download_queue.get()
            if task is None:
                break
            action, data = task
            if action == "search":
                self._worker_search(data)
            elif action == "popular":
                self._worker_popular(data)
            elif action == "random":
                self._worker_random()
            elif action == "download":
                self._worker_download(data)

    def _process_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def _append_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log(self, msg):
        self.log_queue.put(msg)

    def _set_progress(self, current, total):
        if total > 0:
            self.root.after(0, lambda: self.prog_var.set(current / total * 100))

    # ── 搜索 ─────────────────────────────────────────────
    def _do_search(self):
        raw = self.search_var.get().strip()
        if not raw:
            return
        gid = parse_input_to_gallery_id(raw)
        if gid:
            self.download_queue.put(("search", ("id", gid)))
        else:
            self.download_queue.put(("search", ("query", raw)))

    def _do_random(self):
        self.download_queue.put(("random", None))

    def _worker_search(self, data):
        kind, value = data
        try:
            if kind == "id":
                self._log(f"获取本子 #{value}...")
                gallery = self.api.get_gallery(value)
                self.current_results = [gallery]
                self.root.after(0, self._update_results_list)
                self._log(f"找到: {self._get_title(gallery)}")
            else:
                query = value
                self._log(f"搜索: {query}")
                result = self.api.search(query)
                self.current_results = result.get("data", [])[:50]
                self.root.after(0, self._update_results_list)
                self._log(f"找到 {len(self.current_results)} 个结果")
        except Exception as e:
            self._log(f"搜索失败: {e}")
            self.root.after(0, lambda err=str(e): messagebox.showerror("搜索失败", err))

    def _worker_random(self):
        self._log("随机获取...")
        try:
            result = self.api.get_popular("today")
            data = result.get("data", [])
            if data:
                import random
                gallery = random.choice(data)
                self.current_results = [gallery]
                self.root.after(0, self._update_results_list)
                self._log(f"随机: #{gallery['id']} - {self._get_title(gallery)[:30]}")
        except Exception as e:
            self._log(f"随机失败: {e}")

    def _worker_popular(self, params):
        sort = params["sort"]
        lang = params.get("lang", "all")
        self._log(f"加载榜单: {sort}（语言: {lang}）")
        try:
            result = self.api.get_popular(sort, language=lang)
            self.current_results = result.get("data", [])
            self.root.after(0, self._update_results_list)
            self._log(f"榜单加载完成: {len(self.current_results)} 个")
        except Exception as e:
            self._log(f"榜单加载失败: {e}")

    def _do_popular(self):
        sort = self.sort_var.get()
        lang = self.lang_var.get()
        self.download_queue.put(("popular", {"sort": sort, "lang": lang}))

    # ── 结果列表 ─────────────────────────────────────────
    def _get_title(self, g):
        return (g.get("title", {}).get("english")
                or g.get("title", {}).get("japanese")
                or g.get("english_title")
                or g.get("japanese_title")
                or "Unknown")

    def _update_results_list(self):
        self.results_list.delete(0, "end")
        for g in self.current_results:
            gid = g.get("id", "?")
            title = self._get_title(g)[:36]
            pages = g.get("num_pages", 0)
            self.results_list.insert("end", f"#{gid}  {title}  [{pages}P]")

    def _on_result_select(self, event):
        # 单击只切换列表选中项，不加载图片（图片通过网络请求，会严重卡顿）
        sel = self.results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.current_results):
            g = self.current_results[idx]
            # 只显示文字信息，不加载缩略图（缩略图在双击时加载）
            self._preview_gallery_simple_no_image(g)

    def _on_result_double_click(self, event):
        sel = self.results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.current_results):
            g = self.current_results[idx]
            self._preview_gallery_simple(g)  # 显示文字 + 加载缩略图

    def _preview_gallery_simple_no_image(self, g):
        """预览：简化列表对象（无完整 tags），仅文字，不加载图片"""
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        gid = g.get("id", "?")
        title = self._get_title(g)
        pages = g.get("num_pages", 0)
        self.info_text.insert("end", f"ID: #{gid}\n标题: {title}\n页数: {pages}\n")
        self.info_text.configure(state="disabled")
        self.preview_label.configure(image="", text="(双击查看封面)")

    def _preview_gallery_simple(self, g):
        """预览：简化列表对象（无完整 tags），含缩略图"""
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        gid = g.get("id", "?")
        title = self._get_title(g)
        pages = g.get("num_pages", 0)
        self.info_text.insert("end", f"ID: #{gid}\n标题: {title}\n页数: {pages}\n")
        self.info_text.configure(state="disabled")
        self._load_thumbnail_simple(g)

    def _preview_gallery_full(self, g):
        """预览：完整 gallery 对象"""
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        title = self._get_title(g)
        gid = g.get("id", "?")
        pages = g.get("num_pages", 0)
        media_id = g.get("media_id", "")
        info = f"ID: #{gid}\n标题: {title}\n页数: {pages}\nMedia ID: {media_id}\n\n标签:\n"
        for tag in g.get("tags", [])[:15]:
            info += f"  [{tag.get('type','')}] {tag.get('name','')}\n"
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("end", info)
        self.info_text.configure(state="disabled")
        self._load_thumbnail(g)

    def _load_thumbnail_simple(self, g):
        """加载列表项缩略图（使用 thumbnail 字段）"""
        try:
            thumb_path = g.get("thumbnail", "")
            if not thumb_path:
                return
            media_id = g.get("media_id", "")
            if not media_id:
                return
            url = f"https://t.nhentai.net/galleries/{media_id}/thumb.jpg"
            proxies = {"http": self.config.get("proxy", "socks5://127.0.0.1:10808"),
                       "https": self.config.get("proxy", "socks5://127.0.0.1:10808")}
            resp = requests.get(url, proxies=proxies, timeout=15,
                                headers=HEADERS, verify=False)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img = img.resize((160, 220), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=photo, text="", width=0, height=0)
                self.preview_label.image = photo
        except Exception as e:
            self.preview_label.configure(text=f"(预览加载失败)", image="")

    def _load_thumbnail(self, g):
        """加载完整 gallery 缩略图"""
        try:
            url = self.api.get_cover_url(g)
            proxies = {"http": self.config.get("proxy", "socks5://127.0.0.1:10808"),
                       "https": self.config.get("proxy", "socks5://127.0.0.1:10808")}
            resp = requests.get(url, proxies=proxies, timeout=15,
                                headers=HEADERS, verify=False)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img = img.resize((160, 220), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=photo, text="", width=0, height=0)
                self.preview_label.image = photo
        except Exception:
            self.preview_label.configure(text="(预览加载失败)", image="")

    # ── 下载 ─────────────────────────────────────────────
    def _download_selected(self):
        sel = self.results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.current_results):
            g = self.current_results[idx]
            gid = g.get("id")
            if gid:
                self.download_queue.put(("download", gid))

    def _worker_download(self, gallery_id):
        self._log(f"开始下载: #{gallery_id}")
        self.root.after(0, lambda: self.prog_var.set(0))
        try:
            gallery = self.api.get_gallery(gallery_id)
            title = self._get_title(gallery)
            pages = gallery.get("num_pages", 0)

            self._log(f"本子: {title} ({pages}页)")
            image_urls = self.api.get_gallery_images(gallery)

            # 文件夹名称: id + 标题
            folder_name = f"{gallery_id}_{sanitize_folder_name(title)}"
            folder_path = Path(self.config["download_dir"]) / folder_name

            self._log(f"文件夹: {folder_name}")
            self._log(f"下载 {len(image_urls)} 张图片...")

            downloader = ImageDownloader(gallery_id, folder_path, self.config)

            def progress(current, total):
                self.root.after(0, lambda c=current, t=total: self._set_progress(c, t))
                self._log(f"下载进度: {current}/{total}")

            downloaded = downloader.download_sync(image_urls, progress)

            # 检查完整性
            valid = [p for p in downloaded
                     if Path(p).exists() and Path(p).stat().st_size >= 1000]
            self._log(f"下载完成: {len(valid)}/{len(image_urls)} 张有效图片")

            if len(valid) < len(image_urls):
                self._log(f"警告: {len(image_urls) - len(valid)} 张下载失败，跳过 PDF")
                self.root.after(0, lambda: messagebox.showwarning(
                    "下载不完整", f"只下载了 {len(valid)}/{len(image_urls)} 张图片\nPDF 未生成"))
                return

            self._log("生成 PDF...")
            pdf_name = f"{gallery_id}_{sanitize_folder_name(title)}.pdf"
            pdf_path = folder_path / pdf_name

            success = PDFBuilder.create_pdf(valid, str(pdf_path))
            if success:
                add_history(gallery_id, title, str(pdf_path), pages)
                self._log(f"完成: {pdf_path}")
                self.root.after(0, lambda p=str(pdf_path): messagebox.showinfo(
                    "完成", f"PDF 已保存:\n{p}"))
                self.root.after(0, self._refresh_history)
            else:
                self._log("PDF 生成失败")
        except Exception as e:
            self._log(f"下载失败: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda err=str(e): messagebox.showerror("下载失败", err))
        finally:
            self.root.after(0, lambda: self.prog_var.set(0))

    # ── 历史记录 ──────────────────────────────────────────
    def _refresh_history(self):
        self.history_list.delete(0, "end")
        history = load_history()
        for item in history[:50]:
            title = item.get("title", "Unknown")[:25]
            gid = item.get("gallery_id", "?")
            self.history_list.insert("end", f"#{gid} {title}")
        self.history_list.bind("<Double-Button-1>", self._on_history_double_click)

    def _on_history_double_click(self, event):
        sel = self.history_list.curselection()
        if not sel:
            return
        history = load_history()
        idx = sel[0]
        if idx < len(history):
            gid = history[idx].get("gallery_id")
            if gid:
                self.download_queue.put(("search", ("id", gid)))

    # ── 配置 ─────────────────────────────────────────────
    def _browse_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.dir_var.set(path)

    def _save_config(self):
        self.config["download_dir"] = self.dir_var.get()
        save_config(self.config)
        self._log("配置已保存")

    def run(self):
        self.root.mainloop()


# ===================== 启动 =====================
if __name__ == "__main__":
    root = tk.Tk()
    app = NhentaiApp(root)
    app.run()
