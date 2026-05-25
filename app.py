"""Nhentai Downloader - Streamlit 界面"""
import streamlit as st
import asyncio
import time
from pathlib import Path
from datetime import datetime

from api_client import NhentaiAPI
from downloader import ImageDownloader
from pdf_builder import PDFBuilder
from config import load_config, save_config, load_history, add_history
from viewer import OnlineViewer


# 页面配置
st.set_page_config(
    page_title="Nhentai Downloader",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化 session state
if "api" not in st.session_state:
    st.session_state.api = NhentaiAPI()

if "current_gallery" not in st.session_state:
    st.session_state.current_gallery = None

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "download_progress" not in st.session_state:
    st.session_state.download_progress = 0

if "viewing_mode" not in st.session_state:
    st.session_state.viewing_mode = False

if "selected_gallery_id" not in st.session_state:
    st.session_state.selected_gallery_id = None


def render_sidebar():
    """渲染侧边栏"""
    st.sidebar.title("📚 Nhentai Downloader")

    # 配置区
    st.sidebar.subheader("⚙️ 配置")

    config = load_config()

    download_dir = st.sidebar.text_input(
        "下载目录",
        value=config.get("download_dir", str(Path(__file__).parent / "downloads")),
    )

    if st.sidebar.button("💾 保存配置"):
        config["download_dir"] = download_dir
        save_config(config)
        st.sidebar.success("配置已保存！")

    st.sidebar.divider()

    # 搜索区
    st.sidebar.subheader("🔍 搜索")

    search_query = st.sidebar.text_input("输入标号/标题/标签", key="search_input")

    search_cols = st.sidebar.columns(2)
    search_btn = search_cols[0].button("🔎 搜索", use_container_width=True)
    random_btn = search_cols[1].button("🎲 随机", use_container_width=True)

    st.sidebar.divider()

    # 榜单区
    st.sidebar.subheader("📊 榜单")

    sort_options = {"today": "🌅 日榜", "week": "📅 周榜", "month": "📆 月榜"}
    sort_mode = st.sidebar.radio("选择榜单", sort_options, horizontal=True, index=0)

    popular_btn = st.sidebar.button("📈 查看榜单", use_container_width=True)

    st.sidebar.divider()

    # 语言过滤
    st.sidebar.subheader("🌐 语言过滤")

    language_options = {
        "chinese": "🇨🇳 中文",
        "english": "🇬🇧 英文",
        "japanese": "🇯🇵 日文",
        "all": "🌐 全部",
    }
    language_filter = st.sidebar.selectbox(
        "默认筛选语言",
        language_options,
        index=0,
    )

    return {
        "search_query": search_query,
        "search_btn": search_btn,
        "random_btn": random_btn,
        "sort_mode": sort_mode,
        "popular_btn": popular_btn,
        "language_filter": language_filter,
    }


def render_gallery_card(gallery: dict, col):
    """渲染本子卡片"""
    with col:
        try:
            thumb_url = st.session_state.api.get_thumbnail_url(gallery)
            cover_url = st.session_state.api.get_cover_url(gallery)

            # 显示缩略图
            st.image(thumb_url, use_container_width=True)

            # 本子标题
            title = gallery.get("title", {}).get("english", "") or gallery.get("title", {}).get("japanese", "Unknown")
            st.caption(f"**{title[:30]}...**" if len(title) > 30 else f"**{title}**")

            # 标签
            tags = gallery.get("tags", [])[:3]
            tag_names = [t.get("name", "") for t in tags]
            st.caption(f"🏷️ {' | '.join(tag_names)}")

            # 页数
            num_pages = gallery.get("num_pages", 0)
            st.caption(f"📄 {num_pages} 页")

            # 按钮
            if st.button("📖 在线阅读", key=f"view_{gallery['id']}"):
                st.session_state.selected_gallery_id = gallery["id"]
                st.session_state.viewing_mode = True
                st.rerun()

            if st.button("⬇️ 下载", key=f"dl_{gallery['id']}"):
                st.session_state.selected_gallery_id = gallery["id"]
                st.rerun()

        except Exception as e:
            st.error(f"加载失败: {e}")


def search_gallery(query: str, language: str = "chinese"):
    """搜索本子"""
    if not query:
        return

    st.session_state.search_results = []

    with st.spinner("搜索中..."):
        try:
            # 如果是纯数字，按标号搜索
            if query.isdigit():
                gallery = st.session_state.api.get_gallery(int(query))
                st.session_state.search_results = [gallery]
            else:
                # 文本搜索
                result = st.session_state.api.search(query, language=language)
                st.session_state.search_results = result.get("data", [])

            st.session_state.viewing_mode = False

        except Exception as e:
            st.error(f"搜索失败: {e}")


def fetch_popular(sort: str, language: str = "chinese"):
    """获取热门榜单"""
    with st.spinner("加载榜单中..."):
        try:
            result = st.session_state.api.get_popular(sort)
            st.session_state.search_results = result.get("data", [])[:50]
            st.session_state.viewing_mode = False
        except Exception as e:
            st.error(f"获取榜单失败: {e}")


def fetch_random():
    """获取随机本子"""
    with st.spinner("随机获取中..."):
        try:
            result = st.session_state.api.get_popular("today")
            if result.get("data"):
                import random
                gallery = random.choice(result["data"])
                st.session_state.search_results = [gallery]
                st.session_state.viewing_mode = False
        except Exception as e:
            st.error(f"随机获取失败: {e}")


def render_results():
    """渲染搜索结果/榜单"""
    if st.session_state.viewing_mode and st.session_state.selected_gallery_id:
        render_online_viewer()
        return

    results = st.session_state.search_results

    if not results:
        st.info("🔍 使用侧边栏搜索本子或浏览榜单")
        return

    st.subheader(f"📚 找到 {len(results)} 个本子")

    # 网格显示
    cols = st.columns(4)
    for i, gallery in enumerate(results):
        col = cols[i % 4]
        render_gallery_card(gallery, col)


def render_online_viewer():
    """渲染在线阅读界面"""
    gallery_id = st.session_state.selected_gallery_id

    if not gallery_id:
        return

    with st.spinner("加载本子信息..."):
        try:
            gallery = st.session_state.api.get_gallery(gallery_id)
            image_urls = st.session_state.api.get_gallery_images(gallery)

            st.session_state.current_gallery = gallery

            # 显示返回按钮
            if st.button("← 返回列表"):
                st.session_state.viewing_mode = False
                st.rerun()

            # 标题
            title = gallery.get("title", {}).get("english", "") or gallery.get("title", {}).get("japanese", "Unknown")
            st.markdown(f"## {title}")

            # 阅读器
            OnlineViewer.render_viewer(gallery_id, image_urls)

        except Exception as e:
            st.error(f"加载失败: {e}")


def download_gallery(gallery_id: int):
    """下载本子并生成 PDF"""
    with st.spinner("获取本子信息..."):
        try:
            gallery = st.session_state.api.get_gallery(gallery_id)
            title = gallery.get("title", {}).get("english", "") or gallery.get("title", {}).get("japanese", "Unknown")
            num_pages = gallery.get("num_pages", 0)

            st.info(f"📥 开始下载: {title} ({num_pages} 页)")

            # 获取图片 URL
            image_urls = st.session_state.api.get_gallery_images(gallery)

            # 下载图片
            downloader = ImageDownloader(gallery_id)

            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(current, total):
                progress = current / total
                progress_bar.progress(progress)
                status_text.text(f"下载中... {current}/{total}")

            # 同步下载（避免 async 问题）
            downloaded_paths = []
            for i, url in enumerate(image_urls):
                ext = url.split(".")[-1] if "." in url else "webp"
                filepath = downloader.download_dir / f"{i+1}.{ext}"

                if not filepath.exists() or filepath.stat().st_size < 1000:
                    # 同步下载
                    config = load_config()
                    proxy = config.get("proxy", "")
                    proxies = {
                        "http": proxy,
                        "https": proxy,
                    } if proxy else {}
                    import requests
                    resp = requests.get(url, proxies=proxies, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(resp.content)

                downloaded_paths.append(str(filepath))
                progress = (i + 1) / len(image_urls)
                progress_bar.progress(progress)
                status_text.text(f"下载中... {i+1}/{len(image_urls)}")

            # 生成 PDF
            st.info("📑 生成 PDF...")

            config = load_config()
            pdf_filename = f"{gallery_id}_{title[:20]}.pdf"
            pdf_path = Path(config["download_dir"]) / f"{gallery_id}" / pdf_filename

            success = PDFBuilder.create_pdf(downloaded_paths, str(pdf_path))

            if success:
                # 保存历史
                add_history(gallery_id, title, str(pdf_path), num_pages)
                st.success(f"✅ 下载完成！PDF 保存至: {pdf_path}")
            else:
                st.error("❌ PDF 生成失败")

            # 重置状态
            st.session_state.selected_gallery_id = None
            st.session_state.viewing_mode = False

        except Exception as e:
            st.error(f"下载失败: {e}")


def render_history():
    """渲染下载历史"""
    st.divider()
    st.subheader("📜 下载历史")

    history = load_history()

    if not history:
        st.info("暂无下载记录")
        return

    for item in history[:10]:
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])

        with col1:
            st.text(f"#{item['gallery_id']}")

        with col2:
            st.text(item["title"][:40])

        with col3:
            st.text(f"{item['pages']} 页")

        with col4:
            pdf_path = item.get("pdf_path", "")
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📄 PDF",
                        f,
                        file_name=Path(pdf_path).name,
                        key=f"dl_history_{item['gallery_id']}",
                    )
            else:
                st.caption("文件不存在")


def main():
    """主函数"""
    # 渲染侧边栏
    sidebar_state = render_sidebar()

    # 处理搜索
    if sidebar_state["search_btn"] and sidebar_state["search_query"]:
        search_gallery(sidebar_state["search_query"], sidebar_state["language_filter"])

    # 处理随机
    if sidebar_state["random_btn"]:
        fetch_random()

    # 处理榜单
    if sidebar_state["popular_btn"]:
        fetch_popular(sidebar_state["sort_mode"], sidebar_state["language_filter"])

    # 处理下载
    if st.session_state.selected_gallery_id and not st.session_state.viewing_mode:
        download_gallery(st.session_state.selected_gallery_id)

    # 渲染主区域
    render_results()

    # 渲染历史
    render_history()


if __name__ == "__main__":
    main()