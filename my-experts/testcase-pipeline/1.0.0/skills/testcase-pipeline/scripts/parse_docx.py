#!/usr/bin/env python3
"""
PRD文档解析脚本：将 .docx 文件转换为 Markdown + 提取媒体文件。

用法:
    python parse_docx.py <input.docx> <output_dir>

输出:
    <output_dir>/prd_raw.md        - Markdown 原文
    <output_dir>/prd_media/media/  - 提取的图片文件

依赖:
    - pandoc (需要系统安装)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_docx(input_path: str, output_dir: str) -> dict:
    """解析 docx 文件，输出 Markdown 和媒体文件。

    Returns:
        dict: {
            "markdown_path": str,   # 输出的 md 文件路径
            "media_dir": str,       # 媒体文件目录
            "image_files": list,    # 图片文件路径列表
        }
    """
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not input_path.exists():
        print(f"ERROR: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.suffix.lower() == ".docx":
        print(f"ERROR: 输入文件必须是 .docx 格式: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "prd_raw.md"
    media_dir = output_dir / "prd_media"

    # 调用 pandoc 转换
    cmd = [
        "pandoc",
        str(input_path),
        "-o", str(md_path),
        f"--extract-media={media_dir}",
    ]

    print(f"正在解析: {input_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: pandoc 转换失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # 收集图片文件
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
    image_files = []
    media_subdir = media_dir / "media"

    if media_subdir.exists():
        for f in sorted(media_subdir.iterdir()):
            if f.suffix.lower() in image_extensions:
                image_files.append(str(f))

    result_info = {
        "markdown_path": str(md_path),
        "media_dir": str(media_dir),
        "image_files": image_files,
    }

    print(f"解析完成:")
    print(f"  Markdown: {md_path}")
    print(f"  图片数量: {len(image_files)}")
    for img in image_files:
        print(f"    - {Path(img).name}")

    return result_info


def main():
    parser = argparse.ArgumentParser(description="PRD文档解析：docx → Markdown + 媒体文件")
    parser.add_argument("input", help="输入的 .docx 文件路径")
    parser.add_argument("output_dir", help="输出目录")
    args = parser.parse_args()

    parse_docx(args.input, args.output_dir)


if __name__ == "__main__":
    main()
