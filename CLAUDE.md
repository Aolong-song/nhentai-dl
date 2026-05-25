# Nhentai Downloader

nhentai.net 本子下载工具，支持搜索、榜单、下载、PDF 生成。

## 环境要求

- Python 3.10+
- V2RayN 代理（SOCKS5: 127.0.0.1:10808）
- 依赖：`pip install -r requirements.txt`

## 运行（推荐 Web 版）

```bash
cd 00.MyCode/20260509-nhentai-downloader
py run_web.py
```

启动后自动打开浏览器访问 `http://localhost:28473/ui`，包含：
- Web 界面（搜索、榜单、下载进度实时展示）
- FastAPI 后端（localhost:28473）
- tkinter 原生文件夹选择器

## 旧版 GUI

```bash
python gui.py  # Tkinter 原生界面（已不维护）
```

## 核心功能

- 搜索本子（支持：纯数字ID、nhentai链接如 `/g/123456/`、标题模糊搜索）
- 浏览日榜/周榜/月榜（`language:chinese` 标签筛选）
- 语言过滤（中文/英文/日文/全部，默认中文）
- 图片同步下载（3次重试+2秒延迟，SSL错误自动重试，verify=False）
- PDF 生成（Pillow RGB 转换）
- 断点续传（已下载文件跳过，文件夹 `id_标题/`）
- 下载进度 SSE 实时推送
- 配置文件保存到 `%APPDATA%\NhentaiDownloader\`

## 文件结构

| 文件 | 说明 |
|---|---|
| `gui.py` | 旧版 Tkinter GUI（不维护） |
| `gui_new.html` | Web 界面（由 FastAPI 托管） |
| `run_web.py` | **启动入口**（启动 API 服务 + 打开浏览器） |
| `app_new.py` | FastAPI 后端（独立可用） |
| `api_client.py` | API 客户端（独立模块） |
| `pdf_builder.py` | PDF 生成器 |
| `config.py` | 配置和历史管理（PyInstaller 兼容） |
| `NhentaiDownloader_Web.spec` | Web 版 PyInstaller 打包规格 |
| `dist/NhentaiDownloader_Web.exe` | Web 版打包输出 |

### API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 服务状态 |
| GET | `/ui` | Web 界面 HTML |
| GET | `/gallery/{id}` | 获取本子详情 |
| POST | `/search` | 搜索本子 |
| POST | `/popular` | 获取榜单 |
| POST | `/download` | 启动下载（异步） |
| GET | `/download/progress/{id}` | SSE 实时下载进度 |
| GET | `/download/status/{id}` | 下载任务状态 |
| POST | `/select_folder` | 打开 tkinter 文件夹选择器 |
| GET/POST | `/config` | 读取/保存配置 |
| GET | `/history` | 下载历史 |

## 打包

```bash
# Web 版（推荐）
py -m PyInstaller NhentaiDownloader_Web.spec --noconfirm
# 输出: dist/NhentaiDownloader_Web.exe

# 旧版 Tkinter
py -m PyInstaller --noconfirm --onefile --name "NhentaiDownloader" --console gui.py
```

## 技术要点

- API 返回结构：`/search` 返回 `result` 数组（不是 `data`）
- 搜索结果为简化对象（无完整 tags），只有 `tag_ids` 数字数组
- 完整本子详情通过 `/galleries/{id}` 获取，包含 `pages[]` 和 `tags[]`
- SSL 证书验证已禁用（`verify=False`），代理环境下避免证书错误
- PyInstaller 运行时配置写入 `%APPDATA%\NhentaiDownloader\`，确保重启后路径持久化
