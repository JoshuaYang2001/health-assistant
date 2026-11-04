#!/usr/bin/env python3
"""Inspect an explicitly selected CPAP card directory without modifying or reading file contents."""

import argparse
import os
import sys
from pathlib import Path


def inspect_card(root: Path) -> tuple[bool, dict[str, int]]:
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("所选路径不是文件夹")
    root_is_series = root.name.casefold() == "p-series"
    directories = [root] if root_is_series else []
    for current, children, _files in os.walk(root, followlinks=False):
        if root_is_series:
            break
        relative = Path(current).relative_to(root)
        children[:] = [
            name for name in children if not (Path(current) / name).is_symlink()
        ]
        if relative.parts and relative.parts[-1].casefold() == "p-series":
            directories.append(Path(current))
            children[:] = []
        elif len(relative.parts) >= 3:
            children[:] = []
    counts = {suffix: 0 for suffix in (".000", ".001", ".002", ".005")}
    visited = 0
    for directory in directories:
        for current, children, files in os.walk(directory, followlinks=False):
            children[:] = [
                name for name in children if not (Path(current) / name).is_symlink()
            ]
            for name in files:
                visited += 1
                if visited > 100000:
                    raise ValueError("文件数量过多，已停止检查")
                file = Path(current) / name
                if file.is_symlink():
                    continue
                suffix = file.suffix.lower()
                if suffix in counts:
                    counts[suffix] += 1
    return bool(directories), counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="只读检查呼吸机 SD 卡目录，不读取数据内容。"
    )
    parser.add_argument("directory", type=Path, help="SD 卡挂载目录")
    args = parser.parse_args()
    try:
        found, counts = inspect_card(args.directory)
    except (OSError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 1
    print("发现 P-Series 目录：" + ("是" if found else "否"))
    if found:
        print(
            "记录文件数量："
            + ", ".join(f"{key}={value}" for key, value in counts.items())
        )
    print("本操作未读取或修改卡内文件；设备型号、记录内容及导入兼容性仍需实卡验证。")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
