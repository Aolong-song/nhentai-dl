# Nhentai Downloader — 项目状态

> 本文件记录开发演进状态，供后续接手参考。

---

## 当前版本：v2.1（2026-05-26）

### 架构

```
浏览器 ──HTTP──> FastAPI 后端（localhost:28473）
                    │
                    ├── /ui          → FileResponse(gui_new.html)
                    ├── /gallery/{id} → NhentaiAPI.get_gallery()
                    ├── /search       → NhentaiAPI.search()
                    ├── /popular      → NhentaiAPI.get_popular()
                    ├── /download     → 后台线程执行下载，更新 DownloadTask 状态
                    ├── /download/progress/{id} → SSE 流推送进度（多任务并行）
                    ├── /select_folder → tkinter filedialog.askdirectory()
                    └── /history, /config → JSON 文件读写
```

### 文件清单

| 文件 | 角色 | 备注 |
|---|---|---|
| `run_web.py` | **启动入口** | FastAPI 服务 + 自动打开浏览器 |
| `gui_new.html` | Web 前端界面 | 多下载并行进度卡片、Editorial Dark Warm 风格 |
| `api_client.py` | nhentai.net API 封装 | 公共 API，无需 Key，SOCKS5 代理 |
| `pdf_builder.py` | PDF 生成器 | Pillow RGB 转换、RGBA 处理 |
| `config.py` | 配置和历史管理 | PyInstaller 兼容：frozen 时写 `%APPDATA%\NhentaiDownloader\` |
| `build_web.ps1` | 打包脚本 | 输出 `dist/NhentaiDownloader_Web.exe` |
| `NhentaiDownloader_Web.spec` | PyInstaller 规格 | 包含 tkinter / FastAPI / uvicorn 等 hiddenimports |
| `dist/NhentaiDownloader_Web.exe` | 打包输出 | ~34MB，独立运行 |

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

### 多下载并行

- 每个下载任务独立进度卡片（`createProgressCard()` 动态创建）
- SSE 连接按 `gallery_id` 独立管理（`esConnections` Map）
- 进度卡片状态存储在 `progressCards` 对象中
- 下载完成/失败后自动清理 SSE 连接

### 配置持久化

```
# EXE 运行时
%APPDATA%\NhentaiDownloader\
├── config.json          # download_dir, proxy 等
└── download_history.json

# Python 源码运行时
<项目目录>\
├── config.json
└── download_history.json
```

---

## 开发历程

### v1.0 — Tkinter 原版
- `gui.py`：Tkinter 原生界面，搜索/榜单/下载同进程执行
- 问题：界面简陋，无法实时显示下载进度

### v2.0 — Web 版重构
- 新增 `gui_new.html`：独立 HTML/CSS/JS 界面
- 新增 FastAPI 后端提供 REST API
- 问题：HTML 通过 `file://` 打开 PyInstaller 临时目录，路径每次变化

### v2.1 — 打包修复 + SSE 进度（2026-05-11）
- 修复：`get_html_path()` 用 `Path(sys._MEIPASS)` 拼接
- 修复：SSE Generator 内 `time.sleep()` → `await asyncio.sleep()`
- 新增：`/ui` 路由通过 FastAPI FileResponse 托管 HTML
- 新增：tkinter 文件夹选择器（`/select_folder`）

### v2.2 — 多下载并行 + 优化（2026-05-26）
- **新增**：多下载并行进度卡片（各自独立 SSE 连接）
- **修复**：进度卡片 CSS class 选择器冲突（`.progress-count` vs `#progressCount`）
- **删除**：旧 Tkinter 实现（`gui.py`）、Streamlit 实现（`app.py`）、重复 FastAPI（`app_new.py`）
- **优化**：移除 `NHENTAI_API_KEY` 要求（公共 API 无需 Key）
- **更新**：requirements.txt、CLAUDE.md、README.md、PROJECT_STATUS.md

---

## 已知问题 / 待改进

- [ ] PDF 生成后应自动打开文件夹
- [ ] 历史记录按插入顺序而非时间排序
- [ ] 无重试队列：同一本子正在下载时再次点击会返回 `already_downloading`

---

## 运行命令

```bash
# 源码运行
cd 00.MyCode/20260509-nhentai-downloader
py run_web.py

# 打包
py -m PyInstaller NhentaiDownloader_Web.spec --noconfirm
```