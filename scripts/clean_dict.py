#!/usr/bin/env python3
"""
Rime 词库清洗与全局权重归一化工具（无损格式保留版）
能够统一多目录下的词库文件，通过全局两趟（Two-Pass）扫描避免细胞词库权重倒挂，
同时利用 raw_line 保留原文件的分节注释与空行。
"""

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

TARGET_MIN: int = 10
TARGET_MAX: int = 500000


class DictEntry:
  def __init__(
      self,
      text: str,
      code: str,
      weight: Optional[float],
      raw_line: str,
      is_comment: bool = False,
  ):
    self.text = text
    self.code = code
    self.weight = weight
    self.raw_line = raw_line
    self.is_comment = is_comment

  @property
  def key(self) -> Tuple[str, str]:
    return self.text, self.code

  @property
  def is_phrase(self) -> bool:
    """是否为需要参与 Log 对数归一化的多字词组"""
    return (
        not self.is_comment
        and len(self.text) > 1
        and self.weight is not None
        and self.weight > 0
    )


def parse_dict_file(file_path: Path) -> Tuple[List[str], List[DictEntry]]:
  """分离 YAML Header 与 TSV Body，保留空行与注释，校验 YAML 合法性"""
  lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
  header_lines: List[str] = []
  body_lines: List[str] = []
  found_delimiter = False

  for line in lines:
    if not found_delimiter:
      header_lines.append(line)
      if line.rstrip("\r\n") == "...":
        found_delimiter = True
    else:
      body_lines.append(line)

  if not found_delimiter:
    body_lines = header_lines
    header_lines = []

  if header_lines:
    try:
      yaml.safe_load("".join(header_lines))
    except Exception as e:
      print(
          f"[WARN] 文件 {file_path.name} Header YAML 解析异常: {e}",
          file=sys.stderr,
      )

  entries: List[DictEntry] = []
  for line in body_lines:
    stripped = line.strip()
    # 纯空行或注释行打标记，后续原样回填，保证格式与注释零损失
    if not stripped or stripped.startswith("#"):
      entries.append(DictEntry("", "", None, line, is_comment=True))
      continue

    parts = line.rstrip("\r\n").split("\t")
    text = parts[0].strip()
    code = parts[1].strip() if len(parts) > 1 else ""
    weight: Optional[float] = None

    if len(parts) > 2 and parts[2].strip():
      try:
        weight = float(parts[2].strip())
      except ValueError:
        print(
            f"[WARN] 文件 {file_path.name} 包含非法权重值: '{parts[2]}'",
            file=sys.stderr,
        )

    entries.append(
        DictEntry(
            text=text, code=code, weight=weight, raw_line=line, is_comment=False
        )
    )

  return header_lines, entries


def process_dictionaries(
    files: List[Path], min_threshold: float = 2.0, dry_run: bool = False
) -> int:
  parsed_data = {}
  global_min_log = float("inf")
  global_max_log = float("-inf")
  total_raw_count = 0
  total_clean_count = 0

  # Pass 1: 解析、去重、长低频词过滤、统计全局 Log 权重区间
  for file_path in files:
    header_lines, raw_entries = parse_dict_file(file_path)

    comments = [e for e in raw_entries if e.is_comment]
    real_entries = [e for e in raw_entries if not e.is_comment]
    total_raw_count += len(real_entries)

    dedup_map: Dict[Tuple[str, str], DictEntry] = {}
    for entry in real_entries:
      # 过滤长低频词 (len > 4 且 0 < weight < min_threshold)，安全保留 w == 0
      if (
          len(entry.text) > 4
          and entry.weight is not None
          and 0 < entry.weight < min_threshold
      ):
        continue

      key = entry.key
      if key not in dedup_map:
        dedup_map[key] = entry
      else:
        # 重复词条保留较高权重者
        old_w = dedup_map[key].weight or 0
        new_w = entry.weight or 0
        if new_w > old_w:
          dedup_map[key] = entry

    cleaned_real = list(dedup_map.values())
    total_clean_count += len(cleaned_real)

    # 包含真实词条与原位置注释行
    all_cleaned = cleaned_real + comments

    # 统计全局 Log 权重区间 (仅针对多字词组，跳过单字与 <=0 词条)
    for entry in cleaned_real:
      if entry.is_phrase:
        log_w = math.log(entry.weight)
        if log_w < global_min_log:
          global_min_log = log_w
        if log_w > global_max_log:
          global_max_log = log_w

    parsed_data[file_path] = {"header": header_lines, "entries": all_cleaned}

  has_valid_range = (
      global_max_log > global_min_log and math.isfinite(global_min_log)
  )

  # Pass 2: 基于全局 Min/Max 计算对数归一化，写回文件
  for file_path, data in parsed_data.items():
    header_lines = data["header"]
    entries = data["entries"]
    output_lines = list(header_lines)

    for entry in entries:
      # 1. 纯注释/空行：直接原样输出 raw_line，零损失
      if entry.is_comment:
        output_lines.append(entry.raw_line.rstrip("\r\n") + "\n")
        continue

      # 2. 单字保护 / 无权重 / w <= 0：不参与归一化，输出原始整数权重或空
      if not entry.is_phrase:
        norm_weight_str = (
            f"{int(entry.weight)}" if entry.weight is not None else ""
        )
      elif has_valid_range:
        log_w = math.log(entry.weight)
        ratio = (log_w - global_min_log) / (global_max_log - global_min_log)
        norm_weight = int(TARGET_MIN + ratio * (TARGET_MAX - TARGET_MIN))
        norm_weight_str = str(norm_weight)
      else:
        norm_weight_str = str(TARGET_MAX)

      # 3. 拼装 TSV 行
      if norm_weight_str:
        output_lines.append(f"{entry.text}\t{entry.code}\t{norm_weight_str}\n")
      else:
        output_lines.append(f"{entry.text}\t{entry.code}\n")

    if not dry_run:
      file_path.write_text("".join(output_lines), encoding="utf-8")

  reduction_rate = (
      (1 - total_clean_count / total_raw_count) * 100
      if total_raw_count > 0
      else 0
  )
  tag = "DRY-RUN" if dry_run else "DONE"
  print(
      f"[{tag}] 处理文件数: {len(files)} | 原始词条: {total_raw_count} |"
      f" 清洗后: {total_clean_count} | 瘦身率: {reduction_rate:.2f}%"
  )
  if has_valid_range:
    print(
        f"[RANGE] 全局 Log 原始权重映射区间: {math.exp(global_min_log):.1f} ~"
        f" {math.exp(global_max_log):.0f}"
    )
  else:
    print("[RANGE] 未发现可用于归一化的有效词组权重")

  return 0


def main():
  parser = argparse.ArgumentParser(
      description="Rime 词库清洗与全局归一化工具"
  )
  parser.add_argument(
      "--dirs",
      nargs="+",
      default=["cn_dicts", "cn_dicts_common", "cn_dicts_cell"],
      help="需要统一归一化的词库目录列表",
  )
  parser.add_argument(
      "--min-threshold",
      type=float,
      default=2.0,
      help="长词 (len>4) 被剔除的低频权重阈值 (默认 < 2.0)",
  )
  parser.add_argument(
      "--dry-run",
      action="store_true",
      help="仅输出统计分析与瘦身预览，不修改落盘文件",
  )
  args = parser.parse_args()

  existing_dirs = [d for d in args.dirs if Path(d).exists()]
  if not existing_dirs:
    print(f"[ERROR] 指定的目录均不存在: {args.dirs}", file=sys.stderr)
    sys.exit(1)

  missing_dirs = set(args.dirs) - set(existing_dirs)
  if missing_dirs:
    print(f"[WARN] 跳过未找到的目录: {sorted(missing_dirs)}", file=sys.stderr)

  target_files = sorted(
      [
          f
          for d in existing_dirs
          for f in Path(d).glob("**/*.dict.yaml")
          if f.is_file()
      ]
  )

  if not target_files:
    print(f"[WARN] 指定目录下未查找到任何 .dict.yaml 文件", file=sys.stderr)
    sys.exit(0)

  sys.exit(
      process_dictionaries(
          files=target_files,
          min_threshold=args.min_threshold,
          dry_run=args.dry_run,
      )
  )


if __name__ == "__main__":
  main()
