from pathlib import Path
from scripts.clean_dict import (
    parse_dict_file,
    should_keep_entry,
    process_dictionaries,
)


def test_parse_dict_file_with_comments_and_header(tmp_path: Path):
    dict_path = tmp_path / "sample.dict.yaml"
    content = (
        "---\nname: sample\nversion: \"1.0\"\n...\n"
        "# 分节注释\n"
        "苹果\tping guo\t1000\n\n"
        "香蕉\txiang jiao\t500\n"
    )
    dict_path.write_text(content, encoding="utf-8")

    headers, body = parse_dict_file(dict_path)

    assert len(headers) == 4
    assert headers[-1].strip() == "..."
    assert len(body) == 4
    assert body[0].startswith("#")


def test_ladder_filtering_logic():
    # 单字无条件保护
    assert should_keep_entry("字", 0.5, is_cell=False) is True
    assert should_keep_entry("字", 0.5, is_cell=True) is True

    # 基础库过滤
    assert should_keep_entry("测试", 1.0, is_cell=False) is False
    assert should_keep_entry("测试", 3.0, is_cell=False) is True
    assert should_keep_entry("超长测试词", 10.0, is_cell=False) is False
    assert should_keep_entry("超长测试词", 20.0, is_cell=False) is True

    # 细胞库严格过滤
    assert should_keep_entry("测试", 3.0, is_cell=True) is False
    assert should_keep_entry("测试", 6.0, is_cell=True) is True
    assert should_keep_entry("这是一个非常长词", 100.0, is_cell=True) is False


def test_global_normalization_across_multiple_files(tmp_path: Path):
    dir_a = tmp_path / "cn_dicts"
    dir_b = tmp_path / "cn_dicts_cell"
    dir_a.mkdir()
    dir_b.mkdir()

    file_master = dir_a / "master.dict.yaml"
    file_cell = dir_b / "cell.dict.yaml"

    file_master.write_text(
        "---\nname: master\n...\n系统\txt\t800000\n常用\tcy\t50000\n",
        encoding="utf-8",
    )
    file_cell.write_text(
        "---\nname: cell\n...\n竞业\tjy\t191\n废标\tfb\t15\n", encoding="utf-8"
    )

    process_dictionaries([file_master, file_cell], dry_run=False)

    master_lines = file_master.read_text(encoding="utf-8").splitlines()
    cell_lines = file_cell.read_text(encoding="utf-8").splitlines()

    master_dict = dict(
        (line.split("\t")[0], line.split("\t")[2])
        for line in master_lines[3:]
        if "\t" in line
    )
    cell_dict = dict(
        (line.split("\t")[0], line.split("\t")[2])
        for line in cell_lines[3:]
        if "\t" in line
    )

    assert "系统" in master_dict
    assert "竞业" in cell_dict


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