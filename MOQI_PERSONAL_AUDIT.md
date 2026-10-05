# 墨奇·个人自适应版：完整审计与方案说明

## 1. 本次审计范围

已读取你上传的 `moqiall` 分支压缩包，并对仓库结构、运行时 schema、词库入口、Lua 依赖、构建脚本、recipe 与文档进行了交叉审计。

仓库规模：
- 277 个实际文件
- 67 个 YAML/YML
- 53 个 Lua
- 35 个 Python
- 60 个图片及其它资源
- 1 个 7 MB 级别的 `zh-moqi.gram` 二进制语法模型

图片、历史资源和第三方词库属于数据/文档资产，不参与候选排序逻辑；Python 主要负责离线生成词库和发布包。

## 2. 原方案真正的运行链

核心 `moqi_wan_flypymo.schema.yaml` 的实际运行链是：

1. `speller`
   - 小鹤双拼拼写代数
   - `;` 后为墨奇辅助码/其它派生码
   - 同时产生超级简拼、辅助码等派生输入形式。

2. `segmentors`
   - `add_user_dict`：`ac` 显式造词
   - emoji、英文、墨奇反查、部件、笔画等专用分段
   - 普通中文走 `abc_segmentor`

3. `translators`
   - 多个 `custom_phrase` 固定短语层
   - 日期、农历、Unicode、身份证、计算器
   - `add_user_dict`
   - emoji、英文、反查、部件、笔画
   - 主 `table_translator`
   - `script_translator`
   - 原来的 `script_translator@user_dict_set`

4. `filters`
   - 超级注释
   - 墨奇辅助码筛选
   - 简码固定词
   - 用户词标记
   - 墨奇首末码显示
   - OpenCC
   - 长词过滤
   - 最后 `uniquifier`

## 3. 原方案最关键的事实

### 3.1 `ac` 确实是“手动造词”通道

原方案的 `add_user_dict` 同时开启了：
- `enable_user_dict: true`
- `enable_sentence: true`
- `enable_encoder: true`
- `prefix: ac`
- `user_dict: user.custom.dict`

所以 `ac` 是一个专门的显式造词入口，而不是普通输入过程中的无感学习。

### 3.2 主翻译器虽然已经开启动态用户词典，但没有自动造词

原主 `translator` 当前是：
- `enable_user_dict: true`
- `contextual_suggestions: true`
- `enable_completion: false`

但没有：
- `enable_encoder: true`
- `encode_commit_history: true`
- `max_phrase_length`

因此它可以记忆已经存在于用户词典中的词频，却没有把连续提交内容自动编码成新的用户词。

### 3.3 `user_dict_set` 是额外的一条用户词路径

它再次使用：
- `dictionary: moqi_wan.extended`
- `user_dict: user.custom.dict`
- `enable_user_dict: true`

并通过 `script_translator@user_dict_set` 接入。

同时主 `translator` 本身也已经 `enable_user_dict: true`，因此这是两条重叠的动态用户词路径；最终还要经过 `uniquifier` 去重。

个人版已将它移除，统一由主翻译器负责动态词频和自动造词，避免重复候选源。

## 4. 为什么原方案会与你的需求冲突

上游 README 明确把“固定词频”作为默认理念：
- 默认关闭用户词典；
- 用 `ac` 做自造词；
- 这样自造词不会改变系统词频和系统候选顺序。

这和你的目标正好相反：

> 你要的是“输入法逐渐记住我”，而不是“词频永远固定、我手动告诉它造哪个词”。

因此个人版不再把上游“固定词频 + ac”作为核心，而是把它改成：

**静态词库 → 个人动态词频 → 自动新词 → 可选语境模型**

## 5. 新方案的核心改动

新文件：

`moqi_personal_flypymo.schema.yaml`

核心设置：

```yaml
translator:
  contextual_suggestions: false
  dictionary: moqi_wan.extended
  enable_completion: false
  enable_user_dict: true
  enable_encoder: true
  encode_commit_history: true
  max_phrase_length: 5
  enable_sentence: false
  initial_quality: 10000
```

### 5.1 无感动态词频

`enable_user_dict: true` 保留。

每次正常选择候选后，Rime 的用户词典机制会更新提交次数和动态权重。

这不是简单的“把最后选中的词永久置顶”，而是 Rime 自己的动态 user dictionary 机制，会随提交次数、时间衰减等因素计算权重。

### 5.2 自动自生词

真正关键的是：

```yaml
enable_encoder: true
encode_commit_history: true
max_phrase_length: 5
```

这使主 `table_translator` 在正常提交后利用 commit history 自动生成组合词。

也就是说：

你正常输入：

> 岩土 → 工程 → 勘察

连续使用后，系统可以逐渐形成：

> 岩土工程、工程勘察、岩土工程勘察

而不需要：

> `ac...`

这正是你要的“无感自生词”。

### 5.3 不开启“整句智能自动上屏”

这里特意保持：

```yaml
enable_sentence: false
```

原因不是 Rime 做不到，而是你的目标不是把它变成“整句输入法”。

你的目标是：

**词频越来越懂你 + 常用组合词自动形成**

而不是：

**每次输入长句都让语言模型接管候选。**

## 6. 为什么个人版默认关闭 `contextual_suggestions`

原方案：

```yaml
contextual_suggestions: true
```

它会让 grammar/Poet 参与候选重新排序。

这对整句正确率有帮助，但与你提出的：

> 低频系统词不要莫名其妙突然跑到前面

存在结构上的冲突。

因此个人版默认：

```yaml
contextual_suggestions: false
```

让排序主要回到：

**静态词频 + 个人动态词频 + 固定短语层**

如果以后你发现自己更喜欢“语境优先”，只需要把它改回 `true`。

## 7. 为什么没有删除 `ac`

我没有把 `ac` 功能粗暴删除。

它现在的定位变成：

**后备的显式强制造词入口。**

日常输入不需要它。

只有在你希望“这个词现在立刻进入用户词典”时，才使用 `ac`。

这样既满足你的无感学习目标，又不损失原方案的保险机制。

## 8. 原仓库里几个容易误判的模块

### `lua/sbxlm/auto_length.lua`

这是一个相当值得注意的模块。

它确实包含动态 Memory、dynamic user dictionary、提交回调、自动编码等逻辑。

但是在你当前 `moqiall` schema 中，它没有被 engine 直接挂载。

当前真正挂载的只有：

```yaml
lua_processor@*sbxlm.key_binder
```

所以不能把 `auto_length.lua` 当成你当前方案已经启用的自动造词机制。

### `lua/cold_word_drop/*`

这一套是“人工降频/隐藏候选”的独立工具：
- `Control+j` 降频
- `Control+d` 隐藏

它也没有被当前 schema 的 engine 直接启用。

因此它不是你当前候选排序异常的主要原因。

### `lua/is_in_user_dict.lua`

它主要是给：
- `user_phrase` 加 `*`
- `sentence` 加 `∞`

它是显示标记，不负责动态词频计算。

### `lua/stick.lua`

它处理超级简码固定词，读取：

- `custom_phrase_super_1jian.txt`
- `custom_phrase_super_2jian.txt`
- `custom_phrase_super_3jian.txt`

它会把固定简码词放进候选前部/注释。

因此它也不是动态 userdb 的来源。

## 9. 固定短语为什么仍然可能非常靠前

原方案中的：

```yaml
custom_phrase:
  initial_quality: 100001
```

以及：

```yaml
custom_phrase_3_code:
  initial_quality: 100001
```

是故意设计出来的高优先级固定短语层。

这与动态用户词典是两个概念：

- `custom_phrase`：人为预先指定的固定词
- `user.custom.dict`：个人动态学习
- `moqi_wan.extended`：静态系统词库

因此个人版没有把这两个 `100001` 随意改成一个“拍脑袋”的数值。

## 10. 最重要的排序结构

个人版最终形成：

```text
输入
 ↓
小鹤双拼 + 墨奇辅助码
 ↓
候选生成
 ├─ 固定快捷短语
 ├─ 静态系统词库
 ├─ 个人 userdb
 └─ 自动编码产生的新词
 ↓
个人动态权重
 ↓
超级注释 / 辅助码 / OpenCC / 其它过滤器
 ↓
uniquifier
 ↓
候选菜单
```

这里没有人为加入一个“所有用户词一律 +5000”之类的魔法参数。

这是刻意的。

## 11. 与 Rime 引擎实现的对应关系

当前 librime 的 `table_translator` 实现明确支持：
- `enable_user_dict`
- `enable_encoder`
- `encode_commit_history`
- `max_phrase_length`

并且 `Memorize()` 会在提交后更新 user dictionary；开启 `encode_commit_history` 后，还会从最近提交历史组合短语并交给 encoder。

因此这个个人版不是“看起来像自动造词”的 YAML，而是直接打开 Rime 原生的自动编码/学习链路。

## 12. 需要注意的现实边界

这套方案仍然属于“统计式个人记忆”，不是神经网络 AI。

它能做到：

- 记住你经常选什么
- 让个人常用词逐渐获得更合理的动态权重
- 从连续提交历史自动形成组合词
- 对动态词进行时间衰减
- 保留系统词库作为基础

但它不会自动理解：

- “这个词是专有名词”
- “这个词虽然只打一次但以后应该永久置顶”
- “这个组合在语义上非常合理但我还没输入过”

这些属于更高级的预测/语言模型层。

## 13. 交付内容

### 主方案

`moqi_personal_flypymo.schema.yaml`

### 可选方案选单补丁

`default.personal.custom.yaml`

它不会覆盖你现有的 `default.custom.yaml`，只是告诉你如何把个人方案插入方案列表。

### 完整审计说明

本文件。

## 14. 安装方式

把 `moqi_personal_flypymo.schema.yaml` 放进 Rime 用户目录。

如果希望自动加入方案列表，把：

`default.personal.custom.yaml`

中的 patch 合并到你自己的 `default.custom.yaml`。

然后重新部署，选择：

**⚡ 惊鸿·游龙·自适应**

原来的：

**⚡ 惊鸿·游龙**

仍然保留，可以随时回退。

## 15. 最关键的一点

个人版使用的仍然是：

```yaml
user_dict: user.custom.dict
```

所以它不会另起一套完全陌生的个人词典。

你已经产生的 `user.custom.dict` 可以继续作为个人记忆数据使用。

---

## 结论

这次不是简单改一个 `enable_user_dict: true`。

真正完成的是把原方案从：

**固定词频 + ac 手工造词 + 多条用户词路径**

调整为：

**静态词库 + 原生动态词频 + commit-history 自动造词 + 单一主动态词路 + 默认关闭语境重排**

这才和你的“无感动态词频、自生词、不要让低频系统词莫名其妙乱跳”的目标一致。
