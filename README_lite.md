# moqi_lite —— 精简版雾凇·墨奇双拼（moqi_wan_flypymo）

只保留 `moqi_wan_flypymo` 一个方案，用于解决 Android / Xime 上的卡顿。
原仓库 `../rime-moqi` 未做任何改动。

## 部署

1. 备份手机（或电脑）上的 rime 用户目录。
2. **退出输入法**，删除 rime 目录下的 `build/` 文件夹。
3. 把本目录下所有文件覆盖到 rime 用户目录。
4. 重新部署（Deploy）。首次部署需要重建词库和 prism，会慢一些。

> 不要覆盖：`moqi_wan.userdb/`、`default.custom.yaml`、你自己改过的 `custom_phrase/`。

回滚：把备份的 rime 目录拷回，删掉 `build/`，重新部署。

## 与原版的差异

| 项 | 处理 |
| --- | --- |
| 词典编码 | 每条只保留 `拼音;墨奇;` 两段（`moqi_aux` 的 xform 在上屏前就丢掉了后面的字段，行为完全等价） |
| 词库 | 保留 base / ext / 8105 / 41448 / others / user / exthot / idiom / literature / poetry / place / computer / inputmethod / composite |
| 删除 | easy_en、chaifen、mars、ac 造词、围棋、stroke/zrlf/cangjie 反查、9 个 custom_phrase 表、stick 过滤、sbxlm.key_binder、moqi.jianma_show、GB18030-2022 |
| 保留 | emoji、简繁切换、`zh-moqi.gram` 语法模型、用户词典自动学习、长词、诗词、地理、IT 词汇 |
| 体积 | 词典源文件 187.2 MB → 64.3 MB；包 71 MB；1,396,950 条 |

## 本次新增

### 1. `symbols.yaml`

librime 会检查一批「内置文件」，发现用户目录里缺 `symbols.yaml` 就会从 app 里拷一份并在日志里写
`restored missing builtin file: symbols.yaml`。本包补上了原版的 `symbols.yaml`，日志不再出现。
（本方案的 `punctuator` 是写在 schema 里的，所以这个文件只是补齐、不改变任何输入行为。）

### 2. 智能点号 `lua/url_dot.lua`

中文模式下 `.` 默认仍然是「。」，只有下面两种情况输出半角 `.`：

1. 没有组字，且上一次上屏以英文字母 / 数字 / 半角点结尾；
2. 正在组字，输入串是纯英文数字等拉丁字符，且没有任何中文候选（如 `www`），
   或者上一次上屏以半角点结尾（同一个网址的续写，如 `www.` 之后打 `baidu`）。

其余情况（例如打 `nihao` 再按 `.`）完全交回给 `punctuator`，行为和原来一模一样。

安全措施：

- 整个处理包在 `pcall` 里，任何异常都退回原行为；
- 组字里只要已经有标点片段（包括数字后「半选」的小数点）或者已经被选中的候选，就一律不接管；
- 只在 `ascii_punct` / 英文模式都关闭时才生效。

**关闭方法**：删掉 schema 里 `engine/processors` 下的这一行，重新部署即可完全复原：

```yaml
    - "lua_processor@*url_dot"
```

> 注：小键盘 `.` 和主键盘 `.` 在 Rime 里是同一个键码（0x2e），punctuator 无法区分，
> 所以只能按「上下文」判断，不能只改小键盘。

## 重新生成

```bash
python ../build_moqi_lite.py     # 从 ../rime-moqi 重新生成整个 moqi_lite/
python ../validate_lite.py       # 校验 schema / 词库 / 代数等价性
```

## 如果还是卡

按收益从大到小：

1. `translator/contextual_suggestions: false`（整句联想，最耗 CPU）
2. 去掉 `cn_dicts_cell/composite`（32 MB / 62 万条长词）
3. 去掉 `cn_dicts/41448`（4.3 万条生僻字词）
4. `menu/page_size` 再降到 4
