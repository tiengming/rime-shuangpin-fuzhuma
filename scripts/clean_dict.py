#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rime 墨奇音形 (moqiall) 词库清洗与自动化拆分工具
"""

import math
import os
import re
from typing import Dict, List, Tuple

def parse_dict_file(filepath: str) -> Tuple[list, List[dict]]:
    """
    解析 Rime 字典文件，提取 YAML Header 与数据体
    """
    header_lines = []
    entries = []

    if not os.path.exists(filepath):
        return header_lines, entries

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    data_start = False
    for line in lines:
        stripped = line.strip()
        if not data_start:
            header_lines.append(line)
            if stripped == '...':
                data_start = True
            continue

        if not stripped or stripped.startswith('#'):
            continue

        parts = line.rstrip('\r\n').split('\t')
        if len(parts) >= 1:
            text = parts[0].strip()
            code = parts[1].strip() if len(parts) > 1 else ""
            weight_str = parts[2].strip() if len(parts) > 2 else ""

            weight = 0
            if weight_str.isdigit():
                weight = int(weight_str)

            entries.append({
                "text": text,
                "code": code,
                "weight": weight,
                "raw": line
            })

    return header_lines, entries


def normalize_weights_log(entries: List[dict], target_min: int = 10, target_max: int = 1000000) -> List[dict]:
    """
    词频 Log 缩放归一化：
    Scaled = target_min + (log(W + 1) - log(min_W + 1)) / (log(max_W + 1) - log(min_W + 1)) * (target_max - target_min)
    """
    if not entries:
        return entries

    weights = [e['weight'] for e in entries if e['weight'] > 0]
    if not weights:
        for e in entries:
            e['norm_weight'] = target_min
        return entries

    min_w = min(weights)
    max_w = max(weights)

    log_min = math.log(min_w + 1)
    log_max = math.log(max_w + 1)
    denom = log_max - log_min if log_max > log_min else 1.0

    for e in entries:
        if e['weight'] <= 0:
            e['norm_weight'] = target_min
            continue
        log_w = math.log(e['weight'] + 1)
        scaled = target_min + (log_w - log_min) / denom * (target_max - target_min)
        e['norm_weight'] = int(round(scaled))

    return entries


def clean_and_deduplicate(entries: List[dict], min_weight_threshold: int = 0) -> List[dict]:
    """
    词库清洗：过滤低频词，按 (词条, 编码) 唯一键保留最高词频
    """
    seen: Dict[Tuple[str, str], dict] = {}

    for e in entries:
        # 低频词过滤
        if min_weight_threshold > 0 and e['weight'] < min_weight_threshold and e['weight'] > 0 and len(e['text']) > 4:
            continue

        key = (e['text'], e['code'])
        if key not in seen:
            seen[key] = e
        else:
            if e['weight'] > seen[key]['weight']:
                seen[key] = e

    return list(seen.values())


def main():
    print("=== Rime moqiall 词库自动化清洗与规范化工具 ===")
    sample_file = "cn_dicts_common/chengyu.dict.yaml"
    if os.path.exists(sample_file):
        _, entries = parse_dict_file(sample_file)
        print(f"读取 {sample_file}: 共 {len(entries)} 条记录")
        cleaned = clean_and_deduplicate(entries, min_weight_threshold=0)
        print(f"清洗去重后: 共 {len(cleaned)} 条记录")
        normalized = normalize_weights_log(cleaned)
        print("词频归一化完成，示例产物前 3 条:")
        for item in normalized[:3]:
            print(f"  词条: {item['text']} | 编码: {item['code']} | 原始权重: {item['weight']} -> 归一后: {item['norm_weight']}")
    else:
        print("未找到示例词库，脚本骨架就绪。")

if __name__ == "__main__":
    main()
