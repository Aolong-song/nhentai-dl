# Nhentai Downloader

nhentai.net 本子下载工具，支持搜索、榜单浏览、下载和 PDF 生成。

> **⚠️ 注意**：运行前必须配置 `NHENTAI_API_KEY`，否则程序会报错退出。

## 功能特性

- 搜索本子（支持：纯数字 ID、nhentai 链接、标题模糊搜索）
- 浏览日榜/周榜/月榜
- 语言过滤（中文/英文/日文/全部）
- 图片异步下载（支持断点续传）
- PDF 生成（Pillow RGB 转换）
- Streamlit Web 界面

## 环境要求

- Python 3.10+
- nhentai.net API Key
- 网络连接（可能需要代理）

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### 第一步：获取 nhentai.net API Key

1. 访问 [nhentai.net/settings/](https://nhentai.net/settings/)
2. 登录你的账号
3. 页面中找到 **API Key**（格式：`nhk_xxxxxxxx...`）
4. 复制备用

### 第二步：配置 API Key（两种方式选其一）

**方式 A：环境变量（推荐）**

```bash
# Linux / macOS / Git Bash / WSL
export NHENTAI_API_KEY="nhk_这里粘贴你的key"
export HTTP_PROXY="socks5://127.0.0.1:10808"   # 如果需要代理
```

```powershell
# Windows PowerShell
$env:NHENTAI_API_KEY="nhk_这里粘贴你的key"
$env:HTTP_PROXY="socks5://127.0.0.1:10808"
```

```cmd
# Windows CMD
set NHENTAI_API_KEY=nhk_这里粘贴你的key
```

**方式 B：.env 文件（项目根目录）**

```bash
cp .env.example .env
# 用文本编辑器打开 .env，填入你的 API Key
```

> `.env` 文件已加入 `.gitignore`，不会被上传到 GitHub。

## 运行

```bash
streamlit run app.py
```

启动后访问 `http://localhost:8501`

## 项目结构

```
.
├── api_client.py      # nhentai API 客户端
├── app.py             # Streamlit Web 界面
├── downloader.py      # 图片异步下载器
├── pdf_builder.py     # PDF 生成器
├── viewer.py          # 在线阅读器
├── config.py          # 配置和历史管理
├── requirements.txt   # Python 依赖
├── .env.example       # 环境变量模板
└── README.md
```

## 技术说明

- API 返回结构：`/search` 返回 `result` 数组（不是 `data`）
- 搜索结果为简化对象，只有 `tag_ids` 数字数组
- 完整本子详情通过 `/galleries/{id}` 获取
- SSL 证书验证在代理环境下自动处理

## 许可证

MIT License
