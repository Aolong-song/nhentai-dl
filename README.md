# Nhentai Downloader

nhentai.net 本子下载工具，FastAPI + Web UI，支持多线程并行下载进度展示。

## 运行

```bash
cd 00.MyCode/20260509-nhentai-downloader
pip install -r requirements.txt
py run_web.py
```

启动后自动打开浏览器：`http://localhost:28473/ui`

## 功能

- 搜索本子（支持：纯数字 ID、nhentai 链接、标题模糊搜索）
- 浏览日榜/周榜/月榜（`language:chinese` 标签筛选）
- 语言过滤（中文/英文/日文/全部，默认中文）
- 图片同步下载（3次重试 + 断点续传）
- PDF 生成（Pillow RGB 转换）
- **多线程并行下载进度**：可同时启动多个下载，各自有独立进度条
- 下载目录 tkinter 文件夹选择器

## 文件结构

```
├── run_web.py              # 启动入口（FastAPI 服务 + 打开浏览器）
├── gui_new.html            # Web 界面（多下载并行进度）
├── api_client.py           # API 客户端
├── pdf_builder.py          # PDF 生成器
├── config.py               # 配置和历史管理
├── build_web.ps1           # 打包脚本
├── requirements.txt        # Python 依赖
└── dist/
    └── NhentaiDownloader_Web.exe  # 打包后 EXE
```

## 打包

```bash
py -m PyInstaller NhentaiDownloader_Web.spec --noconfirm
# 输出: dist/NhentaiDownloader_Web.exe
```

## 技术说明

- API 返回结构：`/search` 返回 `result` 数组
- 搜索结果为简化对象，只有 `tag_ids` 数字数组
- 完整本子详情通过 `/galleries/{id}` 获取
- SSL 证书验证已禁用（`verify=False`），代理环境下避免证书错误
- PyInstaller 运行时配置写入 `%APPDATA%\NhentaiDownloader\`