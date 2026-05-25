"""PDF 生成器"""
from pathlib import Path
from typing import List
from PIL import Image
import os


class PDFBuilder:
    """PDF 生成器"""

    @staticmethod
    def create_pdf(image_paths: List[str], output_path: str) -> bool:
        """将图片合并为 PDF

        Args:
            image_paths: 图片路径列表（按顺序）
            output_path: 输出 PDF 路径

        Returns:
            是否成功
        """
        if not image_paths:
            return False

        images = []

        for img_path in sorted(image_paths, key=lambda x: int(Path(x).stem or "0")):
            try:
                img = Image.open(img_path)

                # 转换为 RGB（PDF 不支持 RGBA）
                if img.mode in ("RGBA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = background

                # 如果有透明度通道，转换为 RGB
                if img.mode == "P" and "transparency" in img.info:
                    img = img.convert("RGBA")

                images.append(img)
            except Exception as e:
                print(f"处理图片失败 {img_path}: {e}")
                continue

        if not images:
            return False

        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 第一个图片保存为 PDF，多页
            images[0].save(
                output_path,
                "PDF",
                resolution=100.0,
                save_all=True,
                append_images=images[1:],
            )
            return True
        except Exception as e:
            print(f"生成 PDF 失败: {e}")
            return False

    @staticmethod
    def get_pdf_size(image_paths: List[str]) -> int:
        """估算 PDF 大小（MB）"""
        total_size = 0
        for path in image_paths:
            if os.path.exists(path):
                total_size += os.path.getsize(path)
        return total_size / (1024 * 1024)