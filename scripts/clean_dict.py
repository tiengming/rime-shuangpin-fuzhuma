#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
from pathlib import Path

# 识别细胞词库/诗词/长词库的路径关键字
CELL_KEYWORDS = ["cn_dicts_cell", "poetry", "changcijian", "others"]


def is_cell_dict(file_path: Path) -> bool:
    """判断是否为细胞词库或扩展长词库"""
    path_str = str(file_path).replace("\\", "/")
    return any(kw in path_str for kw in CELL_KEYWORDS)


def should_keep_entry(text: str, weight: float, is_cell: bool) -> bool:
    """根据词长、权重和词库类型综合判定词条留存"""
    # 0 或未填权重的词条（如快捷码/辅助码）必须保留
    if weight == 0:
        return True

    length = len(text)

    # 1. 单字无条件保护
    if length == 1:
        return True

    # 2. 细胞词库/扩展长词库（更严格的阶梯过滤）
    if is_cell:
        if length == 2:
            return weight >= 5.0
        elif 3 <= length <= 4:
            return weight >= 12.0
        elif length >= 5:
            return length <= 6 and weight >= 50.0

    # 3. 基础词库（核心通用词库）
    else:
        if length == 2:
            return weight >= 2.0
        elif 3 <= length <= 4:
            return weight >= 5.0
        elif length >= 5:
            return length <= 8 and weight >= 15.0

    return False


def parse_dict_file(file_path: Path):
    """解析 Rime 词库文件，提取 Header 与 Body"""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    header_lines = []
    body_lines = []
    in_header = False
    header_ended = False

    for line in lines:
        stripped = line.strip()

        if not header_ended:
            header_lines.append(line)
            if stripped == "---":
                in_header = True
            elif stripped == "..." and in_header:
                header_ended = True
            continue

        body_lines.append(line)

    return header_lines, body_lines


def process_dictionaries(files, dry_run=False):
    """批量清洗并执行全局权重归一化（完美保留注释与空行）"""
    total_raw_entries = 0
    total_cleaned_entries = 0
    file_items = {}

    # 第一阶段：解析、过滤与统计
    for file_path in files:
        if not file_path.exists():
            continue

        is_cell = is_cell_dict(file_path)
        header_lines, body_lines = parse_dict_file(file_path)

        file_kept_count = 0
        file_raw_count = 0
        items = []

        for line in body_lines:
            stripped = line.strip()
            # 完整保留空行和注释
            if not stripped or stripped.startswith("#"):
                items.append({"type": "raw", "line": line})
                continue

            parts = stripped.split("\t")
            file_raw_count += 1

            text = parts[0]
            code = parts[1] if len(parts) > 1 else ""
            try:
                weight = float(parts[2]) if len(parts) > 2 else 0.0
            except ValueError:
                weight = 0.0

            if should_keep_entry(text, weight, is_cell):
                file_kept_count += 1
                items.append({
                    "type": "entry",
                    "text": text,
                    "code": code,
                    "weight": weight,
                })

        total_raw_entries += file_raw_count
        total_cleaned_entries += file_kept_count
        file_items[file_path] = items

    if total_raw_entries == 0:
        print("[WARN] 未找到有效词条。")
        return

    # 收集所有保留词条的有效权重计算 Log 映射区间
    all_weights = [
        item["weight"]
        for items in file_items.values()
        for item in items
        if item["type"] == "entry" and item["weight"] > 0
    ]
    min_w = min(all_weights) if all_weights else 1.0
    max_w = max(all_weights) if all_weights else 500000.0

    log_min = math.log(min_w) if min_w > 0 else 0
    log_max = math.log(max_w) if max_w > log_min else log_min + 1

    # 设定平滑归一化的目标权重区间
    DEFAULT_FALLBACK_WEIGHT = 10000.0  # 未显式填写权重的词条默认保底权重
    TARGET_MIN = 10000.0              # 对数归一化的最低显示权重
    TARGET_MAX = 500000.0             # 单字/最高频词的最大权重

    print(f"[RANGE] 原始权重区间: {min_w:.1f} ~ {max_w:.1f}")

    # 第二阶段：归一化并落盘
    for file_path, items in file_items.items():
        header_lines, _ = parse_dict_file(file_path)
        output_lines = list(header_lines)

        for item in items:
            if item["type"] == "raw":
                output_lines.append(item["line"])
            elif item["type"] == "entry":
                text = item["text"]
                code = item["code"]
                w = item["weight"]

                if len(text) == 1:
                    norm_w = int(TARGET_MAX)
                elif w > 0:
                    norm_val = TARGET_MIN + (math.log(w) - log_min) / (log_max - log_min) * (TARGET_MAX - TARGET_MIN)
                    norm_w = int(round(norm_val))
                else:
                    # 关键修复：无显式权重的词条赋予 10000 保底权重，绝不设为 0
                    norm_w = int(DEFAULT_FALLBACK_WEIGHT)

                formatted_line = f"{text}\t{code}\t{norm_w}" if code else f"{text}\t\t{norm_w}"
                output_lines.append(formatted_line)

        if not dry_run:
            content = "\n".join(output_lines) + "\n"
            file_path.write_text(content, encoding="utf-8")

    slim_rate = (1 - total_cleaned_entries / total_raw_entries) * 100 if total_raw_entries > 0 else 0
    tag = "[DRY-RUN]" if dry_run else "[DONE]"
    print(f"{tag} 处理文件数: {len(file_items)} | 原始词条: {total_raw_entries} | 清洗后: {total_cleaned_entries} | 瘦身率: {slim_rate:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="墨奇音形词库最优清洗工具")
    parser.add_argument("--dry-run", action="store_true", help="仅预览瘦身结果，不更新文件")
    parser.add_argument("--dir", type=str, default=".", help="词库根目录")
    args = parser.parse_args()

    root_dir = Path(args.dir)
    dict_files = list(root_dir.glob("**/*.dict.yaml"))

    process_dictionaries(dict_files, dry_run=args.dry_run)


if __name__ == "__main__":
    main()