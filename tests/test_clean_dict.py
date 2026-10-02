"""Unit tests for Rime dictionary cleaning and global log normalization."""

from pathlib import Path
from scripts.clean_dict import parse_dict_file, process_dictionaries


def test_parse_dict_file_with_comments_and_header(tmp_path: Path):
  dict_path = tmp_path / "sample.dict.yaml"
  content = (
      "---\nname: sample\nversion: \"1.0\"\n...\n# 分节注释\n苹果\tping"
      " guo\t1000\n\n香蕉\txiang jiao\t500\n"
  )
  dict_path.write_text(content, encoding="utf-8")

  headers, entries = parse_dict_file(dict_path)

  assert len(headers) == 4
  assert headers[-1].strip() == "..."
  assert len(entries) == 4  # 1 注释 + 1 苹果 + 1 空行 + 1 香蕉
  assert entries[0].is_comment
  assert entries[0].raw_line.strip() == "# 分节注释"
  assert entries[1].text == "苹果"
  assert entries[1].weight == 1000.0


def test_deduplication_and_threshold_filtering(tmp_path: Path):
  dict_path = tmp_path / "test_filter.dict.yaml"
  content = (
      "---\nname: test\n...\n"
      "重复词条\tchong fu\t10\n"
      "重复词条\tchong fu\t50\n"
      "这是一个非常超长的测试词条\tchang\t1.5\n"
      "保留零权重词条\tzero\t0\n"
      "单字测试\ta\t100\n"
  )
  dict_path.write_text(content, encoding="utf-8")

  process_dictionaries([dict_path], min_threshold=2.0, dry_run=False)

  lines = dict_path.read_text(encoding="utf-8").splitlines()
  body = "\n".join(lines[3:])

  # 1. 去重保留高权重
  assert "重复词条\tchong fu" in body
  # 2. 超长低频词 len > 4 且 0 < w < 2 被过滤
  assert "这是一个非常超长的测试词条" not in body
  # 3. w == 0 词条保留
  assert "保留零权重词条\tzero\t0" in body
  # 4. 单字保护保留原始数值
  assert "单字测试\ta\t100" in body


def test_global_normalization_across_multiple_files(tmp_path: Path):
  dir_a = tmp_path / "dict_a"
  dir_b = tmp_path / "dict_b"
  dir_a.mkdir()
  dir_b.mkdir()

  file_master = dir_a / "master.dict.yaml"
  file_cell = dir_b / "cell.dict.yaml"

  # 主词库包含极大高频词
  file_master.write_text(
      "---\nname: master\n...\n系统\txt\t800000\n常用\tcy\t50000\n",
      encoding="utf-8",
  )
  # 细胞词库仅有小权重
  file_cell.write_text(
      "---\nname: cell\n...\n竞业\tjy\t191\n废标\tfb\t15\n", encoding="utf-8"
  )

  process_dictionaries([file_master, file_cell], dry_run=False)

  master_lines = file_master.read_text(encoding="utf-8").splitlines()
  cell_lines = file_cell.read_text(encoding="utf-8").splitlines()

  master_dict = dict(
      line.split("\t")[:2] + [line.split("\t")[2]]
      for line in master_lines[3:]
      if "\t" in line
  )
  cell_dict = dict(
      line.split("\t")[:2] + [line.split("\t")[2]]
      for line in cell_lines[3:]
      if "\t" in line
  )

  # 主词库最大值顶格到达 500000
  assert master_dict[("系统", "xt")] == "500000"
  # 细胞词库最小值到 10
  assert cell_dict[("废标", "fb")] == "10"

  # 跨文件断言：竞业 (w=191) 归一化后不会倒挂超出现在高频常用词 (系统 w=800000)
  norm_system = int(master_dict[("系统", "xt")])
  norm_jingye = int(cell_dict[("竞业", "jy")])
  assert norm_jingye < norm_system
  assert norm_jingye < 200000


def test_comment_and_blank_line_preservation(tmp_path: Path):
  dict_path = tmp_path / "comments.dict.yaml"
  content = (
      "---\nname: comments\n...\n"
      "# === 分组一 ===\n"
      "词条一\tci yi\t100\n"
      "\n"
      "# === 分组二 ===\n"
      "词条二\tci er\t200\n"
  )
  dict_path.write_text(content, encoding="utf-8")

  process_dictionaries([dict_path], dry_run=False)

  result = dict_path.read_text(encoding="utf-8")
  assert "# === 分组一 ===" in result
  assert "# === 分组二 ===" in result
  assert "\n\n" in result or "\n# === 分组二 ===" in result
