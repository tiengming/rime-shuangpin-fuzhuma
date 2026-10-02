#!/usr/bin/env python3
"""
Rime 词库清洗与权重归一化工具
修复要点：
1. 全局两趟（Two-Pass）扫描归一化，防止细胞词库权重异常拉伸。
2. 严谨解析 Header (以单独成行的 '...' 划分) 与 TSV Body。
3. 容错处理权重解析（正确支持负数、小数，防静默污染）。
4. 保护单字与 w=0 词条。
"""

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml


TARGET_MIN = 10
TARGET_MAX = 500000


class DictEntry:
    def __init__(self, text: str, code: str, weight: Optional[float], raw_line: str):
        self.text = text
        self.code = code
        self.weight = weight
        self.raw_line = raw_line

    @property
    def key(self) -> Tuple[str, str]:
        return self.text, self.code


def parse_dict_file(file_path: Path) -> Tuple[List[str], List[DictEntry]]:
    """分离 Header (YAML) 与 TSV 正文，校验 Header 合法性"""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines = []
    body_lines = []
    found_delimiter = False

    for line in lines:
        if not found_delimiter:
            header_lines.append(line)
            if line.rstrip("\r\n") == "...":
                found_delimiter = True
        else:
            body_lines.append(line)

    # 如果没找到独立的 '...' 终止符，说明无合规 Header，全量归为 Body
    if not found_delimiter:
        body_lines = header_lines
        header_lines = []

    # 校验 Header YAML
    if header_lines:
        try:
            yaml.safe_load("".join(header_lines))
        except Exception as e:
            print(f"[WARN] {file_path.name} Header YAML 解析异常: {e}", file=sys.stderr)

    # 解析 Body TSV
    entries = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # 空行及全行注释直接跳过或作为结构保留

        parts = line.rstrip("\r\n").split("\t")
        text = parts[0].strip()
        code = parts[1].strip() if len(parts) > 1 else ""
        weight = None

        if len(parts) > 2 and parts[2].strip():
            try:
                weight = float(parts[2].strip())
            except ValueError:
                print(f"[WARN] 文件 {file_path.name} 包含非法权重值: '{parts[2]}'", file=sys.stderr)
                weight = None

        entries.append(DictEntry(text=text, code=code, weight=weight, raw_line=line))

    return header_lines, entries


def process_dictionaries(files: List[Path], dry_run: bool = False):
    parsed_data = {}
    
    # 第一趟 Pass 1: 解析、去重、过滤长低频词、收集全局 Log 权重 Min/Max
    global_min_log = float("inf")
    global_max_log = float("-inf")
    total_raw_count = 0
    total_clean_count = 0

    for file_path in files:
        header_lines, raw_entries = parse_dict_file(file_path)
        total_raw_count += len(raw_entries)

        # 去重与清洗
        dedup_map: Dict[Tuple[str, str], DictEntry] = {}
        for entry in raw_entries:
            # 规则：过滤长低频词 (len > 4 且 0 < w < 2)；保留 w == 0
            if len(entry.text) > 4 and entry.weight is not None and 0 < entry.weight < 2:
                continue

            key = entry.key
            if key not in dedup_map:
                dedup_map[key] = entry
            else:
                # 出现重复项，保留高权重者
                old_w = dedup_map[key].weight or 0
                new_w = entry.weight or 0
                if new_w > old_w:
                    dedup_map[key] = entry

        cleaned_entries = list(dedup_map.values())
        total_clean_count += len(cleaned_entries)

        # 统计全局 Log 权重区间 (跳过单字保护项与 w <= 0)
        for entry in cleaned_entries:
            if len(entry.text) > 1 and entry.weight is not None and entry.weight > 0:
                log_w = math.log(entry.weight)
                if log_w < global_min_log:
                    global_min_log = log_w
                if log_w > global_max_log:
                    global_max_log = log_w

        parsed_data[file_path] = {
            "header": header_lines,
            "entries": cleaned_entries
        }

    # 第二趟 Pass 2: 使用全局 Min/Max 计算对数归一化，写入文件
    has_valid_range = global_max_log > global_min_log

    for file_path, data in parsed_data.items():
        header_lines = data["header"]
        entries = data["entries"]
        output_lines = list(header_lines)

        for entry in entries:
            # 单字保护 或 无权重 / 零权重：保留原始权重或不作缩放
            if len(entry.text) == 1 or entry.weight is None or entry.weight <= 0:
                norm_weight_str = f"{int(entry.weight)}" if entry.weight is not None else ""
            elif has_valid_range:
                log_w = math.log(entry.weight)
                ratio = (log_w - global_min_log) / (global_max_log - global_min_log)
                norm_weight = int(TARGET_MIN + ratio * (TARGET_MAX - TARGET_MIN))
                norm_weight_str = str(norm_weight)
            else:
                norm_weight_str = str(TARGET_MAX)

            # 重新拼装 TSV 行
            if norm_weight_str:
                line_str = f"{entry.text}\t{entry.code}\t{norm_weight_str}\n"
            else:
                line_str = f"{entry.text}\t{entry.code}\n"
            
            output_lines.append(line_str)

        if not dry_run:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(output_lines)

    reduction_rate = (1 - total_clean_count / total_raw_count) * 100 if total_raw_count > 0 else 0
    print(f"[STAT] 原始词条: {total_raw_count} | 清洗后: {total_clean_count} | 瘦身率: {reduction_rate:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="Rime 词库清洗与全局归一化")
    parser.add_argument("--dry-run", action="store_true", help="仅查看瘦身与统计结果，不修改文件")
    parser.add_argument("--dir", type=str, default="cn_dicts", help="词库目录路径")
    args = parser.parse_args()

    dict_dir = Path(args.dir)
    if not dict_dir.exists():
        print(f"[ERROR] 目标目录不存在: {dict_dir}", file=sys.stderr)
        sys.exit(1)

    files = list(dict_dir.glob("**/*.dict.yaml"))
    if not files:
        print(f"[WARN] 未找到任何 .dict.yaml 文件于 {dict_dir}")
        return

    process_dictionaries(files, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
