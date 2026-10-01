#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rime 墨奇音形 (moqiall) 词库自动化清洗、去重与词频归一化工具 (生产级)
"""

import argparse
import glob
import math
import os
import sys
from typing import Dict, List, Tuple


def parse_dict_file(filepath: str) -> Tuple[List[str], List[dict]]:
    """解析 Rime 字典文件，严格分离 YAML Header 与 TSV 数据体"""
    header_lines = []
    entries = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data_start = False
    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not data_start:
            header_lines.append(line)
            if stripped == "...":
                data_start = True
            continue

        if not stripped or stripped.startswith("#"):
            continue

        parts = line.rstrip("\r\n").split("\t")
        if len(parts) >= 1:
            text = parts[0].strip()
            code = parts[1].strip() if len(parts) > 1 else ""
            weight_str = parts[2].strip() if len(parts) > 2 else ""

            weight = 0
            if weight_str.isdigit():
                weight = int(weight_str)

            entries.append(
                {
                    "text": text,
                    "code": code,
                    "weight": weight,
                    "line_no": line_idx,
                }
            )

    return header_lines, entries


def clean_and_deduplicate(
    entries: List[dict], min_weight_threshold: int = 0
) -> List[dict]:
    """词库清洗：按 (词条, 编码) 唯一键保留最高词频，过滤长低频词"""
    seen: Dict[Tuple[str, str], dict] = {}

    for e in entries:
        # 过滤策略：词长 > 4 且权重低于阈值的长词噪音
        if (
            min_weight_threshold > 0
            and len(e["text"]) > 4
            and 0 < e["weight"] < min_weight_threshold
        ):
            continue

        key = (e["text"], e["code"])
        if key not in seen:
            seen[key] = e
        else:
            if e["weight"] > seen[key]["weight"]:
                seen[key] = e

    return list(seen.values())


def normalize_weights_log(
    entries: List[dict], target_min: int = 10, target_max: int = 500000
) -> List[dict]:
    """词频 Log 归一化：区分单字与词组，防止单字权重被压制倒挂"""
    if not entries:
        return entries

    phrase_entries = [
        e for e in entries if len(e["text"]) > 1 and e["weight"] > 0
    ]
    if not phrase_entries:
        for e in entries:
            e["norm_weight"] = e["weight"] if e["weight"] > 0 else target_min
        return entries

    weights = [e["weight"] for e in phrase_entries]
    min_w, max_w = min(weights), max(weights)

    log_min = math.log(min_w + 1)
    log_max = math.log(max_w + 1)
    denom = log_max - log_min if log_max > log_min else 1.0

    for e in entries:
        if len(e["text"]) == 1:
            # 单字保护：不进行 Log 压缩，保持原高权重或赋顶格分
            e["norm_weight"] = e["weight"] if e["weight"] > 0 else target_max
            continue

        if e["weight"] <= 0:
            e["norm_weight"] = target_min
            continue

        log_w = math.log(e["weight"] + 1)
        scaled = target_min + (log_w - log_min) / denom * (
            target_max - target_min
        )
        e["norm_weight"] = int(round(scaled))

    return entries


def write_dict_file(
    filepath: str, header_lines: List[str], entries: List[dict]
):
    """将清洗并归一化后的数据以标准 TSV(Tab分隔) 格式写回磁盘"""
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        for h in header_lines:
            f.write(h)

        for e in entries:
            weight = e.get("norm_weight", e["weight"])
            if e["code"]:
                if weight > 0:
                    f.write(f"{e['text']}\t{e['code']}\t{weight}\n")
                else:
                    f.write(f"{e['text']}\t{e['code']}\n")
            else:
                f.write(f"{e['text']}\n")


def process_directory(
    target_dirs: List[str], min_threshold: int = 0, dry_run: bool = False
):
    """递归遍历处理目标目录下的所有 .dict.yaml 文件"""
    total_files = 0
    total_raw_entries = 0
    total_cleaned_entries = 0

    for target_dir in target_dirs:
        pattern = os.path.join(target_dir, "**", "*.dict.yaml")
        files = glob.glob(pattern, recursive=True)

        for filepath in files:
            total_files += 1
            header, entries = parse_dict_file(filepath)
            raw_cnt = len(entries)
            total_raw_entries += raw_cnt

            cleaned = clean_and_deduplicate(
                entries, min_weight_threshold=min_threshold
            )
            normalized = normalize_weights_log(cleaned)
            clean_cnt = len(normalized)
            total_cleaned_entries += clean_cnt

            opt_rate = (1 - clean_cnt / raw_cnt) * 100 if raw_cnt > 0 else 0
            print(
                f"[{'DRY-RUN' if dry_run else 'PROCESSED'}] {filepath}: {raw_cnt} -> {clean_cnt} 条 (优化率: {opt_rate:.1f}%)"
            )

            if not dry_run:
                write_dict_file(filepath, header, normalized)

    print(
        f"\n=== 处理完成汇总 ===\n"
        f"处理文件数: {total_files} 个\n"
        f"原始词条总数: {total_raw_entries}\n"
        f"清洗后词条数: {total_cleaned_entries}\n"
        f"整体瘦身率: {((1 - total_cleaned_entries / (total_raw_entries or 1)) * 100):.2f}%\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rime 墨奇音形词库自动化清洗与重构工具"
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=["cn_dicts", "cn_dicts_common", "cn_dicts_cell"],
        help="待清洗的词库目录列表",
    )
    parser.add_argument(
        "--min-threshold",
        type=int,
        default=2,
        help="长低频词过滤阈值(默认 <2 过滤)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="试运行模式，不改写磁盘文件"
    )

    args = parser.parse_args()

    valid_dirs = [d for d in args.dirs if os.path.exists(d)]
    if not valid_dirs:
        print(f"提示: 未找到指定目录 {args.dirs}，跳过处理。")
        sys.exit(0)

    process_directory(
        valid_dirs, min_threshold=args.min_threshold, dry_run=args.dry_run
    )
