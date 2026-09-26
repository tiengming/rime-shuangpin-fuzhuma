# 墨奇+小鹤双拼·墨奇方案自由配置指南 (`CONFIG_GUIDE.md`)

本指南旨在帮助用户了解并个性化配置 `moqi_wan_flypymo` 方案（墨奇+小鹤双拼·墨奇）。通过修改方案配置文件（如 `moqi_wan_flypymo.schema.yaml`、`default.custom.yaml` 及相关 Lua 脚本），你可以灵活调整超级注释、辅助码交互、词库频次以及高效快捷键。

---

## 1. 超级注释与辅助码开关 (`pro_comment_format.lua`)

方案集成了 `pro_comment_format.lua` 超级注释模块，可在候选词旁动态显示辅助码、拼音及错音错词提示。配置位于 `moqi_wan_flypymo.schema.yaml` 顶部的 `pro_comment_format:` 节点下：

```yaml
pro_comment_format:
  fuzhu_code: true                    # 辅助码提醒开关：true 开启，false 关闭（熟练辅助码后可设为 false）
  candidate_length: 1                 # 辅助码提醒生效的候选词长度：1 表示仅对单字显示辅助码提示，0 为关闭
  fuzhu_type: moqi                    # 辅助码匹配类型：指定为 moqi (墨奇码)

  corrector: true                     # 错音错词提醒开关：例如输入 geiyu (给予) 时获得 jiyu 纠正提示
  corrector_type: "{comment}"         # 提示格式模板，如写为 "【{comment}】"
```

---

## 2. 辅助码交互调整

### (1) 分号与斜杠选词
- **分号 `;` 选次选**：在 `key_binder/bindings` 中配置 `- { when: has_menu, accept: semicolon, send: 2 }`，按下分号即可直接上屏第 2 候选。
- **斜杠 `/` 选三选**：如需使用 `/` 上屏第 3 候选，可取消 `key_binder/bindings` 中 `- { when: has_menu, accept: slash, send: 3 }` 的注释。

### (2) Tab 键引导辅助码
- 默认输入中，单字符加 `[` 或 `Tab` 可进入辅助码筛选状态。
- 若要在打出音节后按 `Tab` 键直接发送 `[` 引导辅助码，可在 `key_binder/bindings` 中启用：
  ```yaml
  - { when: composing, accept: Tab, send: '[' }
  ```

### (3) 选字与自动上屏逻辑 (`speller`)
- **非自动上屏设计**：`speller/auto_select: false`，避免重码时误上屏。
- **编码与符号分隔**：`speller/alphabet` 包含 `zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA`'`/|`，其中包含反斜杠、竖线与反引号，确保引导符正常生效。

---

## 3. 词库与词频配置

### (1) 自定义短语词库维护 (`custom_phrase/`)
方案支持多种级别的静态短语和常用词表，文件存储在 `custom_phrase/` 目录下：
- `custom_phrase.txt`：通用用户自定义短语（如常用地址、邮箱、固定口令）。格式为 `短语<tab>编码<tab>权重`。
- `custom_phrase_3_code.txt`：3 码出简让全词表。
- `custom_phrase_super_1jian.txt` ~ `custom_phrase_super_3jian.txt`：Tab 快捷出词/字集。
- `custom_phrase_kf.txt`：快符词表。
- `custom_phrase_mqzg.txt`：墨奇字根词表。

> **维护建议**：直接修改对应 `.txt` 文件，保存后在输入法中重新部署（Deploy）即可生效。

### (2) 自动调频与用户词典 (`enable_user_dict`)
- **静态词频（推荐）**：默认 `translator/enable_user_dict: false`，词频保持静态稳定，不随打字顺序乱变，适合追求固定记忆击键体验的用户。
- **动态调频（自动记忆）**：若希望输入法自动记忆你的习惯词频和自造词，可将 `moqi_wan_flypymo.schema.yaml` 中的 `translator/enable_user_dict` 修改为 `true`：
  ```yaml
  translator:
    enable_user_dict: true
  ```

---

## 4. 快捷键指南与高效输入技巧 (`key_binder`)

方案在 `key_binder/bindings` 中定义了一系列高效的键盘映射与操作指令：

### (1) 音节移动与编辑
- `Control + m`：回车直接上屏当前输入的编码字符串。
- `Control + w`：删除光标前的一个完整音节。
- `Control + i`：光标向右移动一个音节 (`Shift+Right`)。
- `Control + o`：光标向左移动一个音节 (`Shift+Left`)。

### (2) 快捷开关 (OpenCC 拆分与翻译)
- `Control + p`：动态切换候选首字的**墨奇码拆分图解**显示（开启/关闭）。
- `Control + l`：动态切换整词所有单字的**墨奇码拆分图解**显示。
- `Control + e`：动态切换中英互译提示（输出中文时显示英文翻译候选）。

### (3) 跨音节插入辅助码 (`Control + 1 ~ 7`)
在一次性输入多字整句/多音节短语（如 `uiyuiyuiy`）后，无需手动按方向键移动光标，使用 `Control + 数字` 可直接在指定位置插入辅助码引导符 `[`：
- `Control + 1`：移动到第 1 个音节末尾并插入 `[`
- `Control + 2`：移动到第 2 个音节末尾并插入 `[`
- `Control + 3 ~ 7`：依此类推，精确补充整句中任意词组的辅助码。

### (4) 首字大写自动首字加辅 (`Shift + A ~ Z`)
在多音节输入过程中，直接按 **`Shift + 字母`**（例如 `Shift + U`），系统会自动将小写的 `u` 辅助码添加到**整句第一个音节**末尾，实现一键快速过滤首字重码。

---

*以上配置支持在 Rime 用户目录下的 `moqi_wan_flypymo.custom.yaml` 或 `default.custom.yaml` 中通过 `patch` 进行无侵入式扩展。*
