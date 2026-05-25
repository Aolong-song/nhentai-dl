"""在线阅读器"""
import streamlit as st
from pathlib import Path
from typing import List, Optional


class OnlineViewer:
    """在线阅读器"""

    @staticmethod
    def render_viewer(gallery_id: int, image_urls: List[str], start_page: int = 1):
        """渲染在线阅读界面

        Args:
            gallery_id: 本子 ID
            image_urls: 图片 URL 列表
            start_page: 起始页码
        """
        if "viewer_page" not in st.session_state:
            st.session_state.viewer_page = start_page

        total = len(image_urls)
        current = st.session_state.viewer_page

        # 工具栏
        col_prev, col_page, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button("⬅️ 上一页", key="prev_page") and current > 1:
                st.session_state.viewer_page -= 1
                st.rerun()

        with col_page:
            st.markdown(f"### 📖 第 {current} / {total} 页")

        with col_next:
            if st.button("下一页 ➡️", key="next_page") and current < total:
                st.session_state.viewer_page += 1
                st.rerun()

        # 显示当前页图片（使用缩略图 URL 预览，正式阅读加载原图）
        if 0 < current <= total:
            image_url = image_urls[current - 1]
            # 使用缩略图作为预览，减少加载时间
            thumb_url = image_url.replace("/i.nhentai.net/", "/t.nhentai.net/")

            col_img, _ = st.columns([3, 1])
            with col_img:
                st.image(thumb_url, use_container_width=True)

        # 键盘快捷键说明
        st.markdown("---")
        st.caption("💡 使用键盘 ← → 或 J K 翻页")

    @staticmethod
    def render_grid_view(image_urls: List[str], cols: int = 4):
        """网格预览模式

        Args:
            image_urls: 图片 URL 列表
            cols: 列数
        """
        thumbs = []
        for url in image_urls:
            thumb_url = url.replace("/i.nhentai.net/", "/t.nhentai.net/")
            thumbs.append(thumb_url)

        # 分行显示
        rows = [thumbs[i:i+cols] for i in range(0, len(thumbs), cols)]

        for row in rows:
            cols_list = st.columns(cols)
            for i, thumb in enumerate(row):
                with cols_list[i]:
                    st.image(thumb, use_container_width=True)