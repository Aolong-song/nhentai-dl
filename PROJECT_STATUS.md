# 项目状态记录

> 本文件记录 Nhentai Downloader 的开发演进状态，供后续接手参考。

---

## 当前版本：v2.1 Web 版（2026-05-11）

### 架构

```
浏览器 ──HTTP──> FastAPI 后端（localhost:28473）
                    │
                    ├── /ui          → FileResponse(gui_new.html) 托管 HTML
                    ├── /gallery/{id} → NhentaiAPI.get_gallery()
                    ├── /search       → NhentaiAPI.search()
                    ├── /popular      → NhentaiAPI.get_popular()
                    ├── /download     → 后台线程执行下载，更新 DownloadTask 状态
                    ├── /download/progress/{id} → SSE 流推送进度
                    ├── /select_folder → tkinter filedialog.askdirectory()
                    └── /history, /config → JSON 文件读写
```

### 文件清单

| 文件 | 角色 | 备注 |
|---|---|---|
| `run_web.py` | **启动入口** | 启动 FastAPI + 打开浏览器 |
| `app_new.py` | FastAPI 路由定义 | 与 run_web.py 基本相同（独立运行备用） |
| `gui_new.html` | Web 前端界面 | FastAPI 通过 `/ui` 托管 |
| `api_client.py` | nhentai.net API 封装 | SOCKS5 代理、SSL 验证关闭 |
| `pdf_builder.py` | PDF 生成器 | Pillow RGB 转换 |
| `config.py` | 配置和历史管理 | PyInstaller 兼容：frozen 时写 `%APPDATA%\NhentaiDownloader\` |
| `gui.py` | 旧版 Tkinter GUI | **已不维护** |
| `NhentaiDownloader_Web.spec` | PyInstaller 打包规格 | 包含 tkinter 等 hiddenimports |
| `dist/NhentaiDownloader_Web.exe` | 最新打包输出 | ~34MB，Web 版独立运行 |

### API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 服务状态 |
| GET | `/ui` | Web 界面（FileResponse） |
| GET | `/gallery/{id}` | 获取本子完整信息 |
| POST | `/search` | 搜索（支持 ID/链接/标题） |
| POST | `/popular` | 榜单（sort: today/week/month, language: chinese/english/japanese/all） |
| POST | `/download` | 启动异步下载，返回 task_id |
| GET | `/download/progress/{id}` | SSE 流，500ms 间隔推送进度 |
| GET | `/download/status/{id}` | 查询任务当前状态 |
| POST | `/select_folder` | 调用 tkinter 文件选择器并保存路径 |
| GET/POST | `/config` | 读取/写入 config.json |
| GET | `/history` | 下载历史列表 |

### 进度推送机制

- 下载在后台 `threading.Thread` 中执行，不阻塞 ASGI 事件循环
- SSE Generator 内使用 `await asyncio.sleep(0.5)`（不能用 `time.sleep()`，会阻塞事件循环）
- 状态变化时推送完整 `DownloadTask.to_dict()` JSON
- 前端 EventSource 收到 `done`/`error` 后**立即**关闭 SSE 连接

### 配置持久化

```
# EXE 运行时
%APPDATA%\NhentaiDownloader\
├── config.json          # download_dir, proxy 等
└── download_history.json

# Python 直接运行时
<项目目录>\
├── config.json
└── download_history.json
```

---

## 开发历程

### v1.0 — Tkinter 原版
- `gui.py`：Tkinter 原生界面，搜索/榜单/下载同进程执行
- `api_client.py`：API 封装
- 问题：界面简陋，无法实时显示下载进度

### v2.0 — Web 版重构
- 新增 `gui_new.html`：独立 HTML/CSS/JS 界面（Editorial Dark Warm 风格）
- 新增 `app_new.py`：FastAPI 后端，提供 REST API
- 问题：HTML 通过 `file://` 打开 PyInstaller 临时目录，路径每次变化

### v2.1 — 打包修复 + 进度 SSE（2026-05-11）
- 修复：`get_html_path()` 用 `Path(sys._MEIPASS)` 拼接，解决 `TypeError`
- 修复：SSE Generator 内 `time.sleep()` → `await asyncio.sleep()`
- 修复：`DownloadTask.update()` 缺少 `result`/`error` 参数
- 修复：下载完成后 EventSource 未立即关闭，进度条卡住
- 修复：config.py 中 `datetime` 未 import，`add_history` 使用错误路径
- 新增：`/ui` 路由通过 FastAPI FileResponse 托管 HTML，不再用 `file://`
- 新增：tkinter 文件夹选择器（`/select_folder`）

---

## 已知问题 / 待改进

- [ ] `app_new.py` 与 `run_web.py` 代码重复，应合并
- [ ] `gui.py`（Tkinter 版）已不维护，可考虑移除
- [ ] 历史记录中 `download_date` 存的是 ISO 字符串，排序按插入顺序而非时间
- [ ] 无重试队列：同一本子正在下载时再次点击会返回 `already_downloading`
- [ ] PDF 生成后应自动打开文件夹

---

## 运行命令

```bash
# 源码运行（开发）
cd 00.MyCode/20260509-nhentai-downloader
py run_web.py

# 打包
py -m PyInstaller NhentaiDownloader_Web.spec --noconfirm
# 输出: dist/NhentaiDownloader_Web.exe

# EXE 运行时，配置文件在：
# %APPDATA%\NhentaiDownloader\
```
