# Comfyui-Promote-Cleaner

面向 **Anima Base** 的提示词清洁节点：把从 Danbooru 等站点复制来的「老式下划线标签」一键洗成模型能直接吃的标准格式。

* **零第三方依赖**，只用 Python 标准库
* 使用 ComfyUI **V3 节点 API**（`comfy_api.latest`），已在 **ComfyUI 0.35.0** 实测加载通过
* 纯文本进、文本出；另附一条直通 `CONDITIONING` 的编码通路
* **多路文本输入**：`text_in` 常驻口 + 最多 10 个可自由增减的额外口 + `text` 文本框，全部按顺序拼接后一起清洁
* **大按钮 + 设置弹窗**：`bracket_policy` / `keep_weights` / `blacklist` 等 9 个开关收进「⚙ 清洁设置」窗口，节点上只留一行设置摘要
* 清洗结果**直接显示在节点上**，不用另接预览节点
* 权重语法 `(tag:1.2)`、`((tag:1.2))` **原样保留**，不会被当作字面括号转义
* 界面文案走**官方 i18n**（`locales/zh/nodeDefs.json`），并自带 `docs/` 帮助页

## 效果示例

| 输入 | 输出 |
| --- | --- |
| `drawing_bow` | `drawing bow` |
| `sunna (zenless zone zero)` | `sunna \(zenless zone zero\)` |
| `sunna_(zenless_zone_zero)` | `sunna \(zenless zone zero\)` |
| `(best_quality:1.3)` | `(best quality:1.3)`（权重保留，只规整内部文本） |
| `((very_aesthetic:1.15))` | `((very aesthetic:1.15))`（嵌套权重也保留） |
| `masterpiece, best_quality, 1girl, tagme, year 2024` | `masterpiece, best quality, 1girl` |

## 安装

把整个 `Comfyui-Promote-Cleaner` 文件夹放进 `ComfyUI/custom_nodes/`，重启 ComfyUI 即可。

也可以在 `ComfyUI/custom_nodes/` 里直接克隆：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/L134283/comfyui-promote-cleaner
```

更新：`cd Comfyui-Promote-Cleaner && git pull`（前端 JS 有缓存，更新后记得 Ctrl+F5）。

本插件无第三方依赖，**不需要** 额外 `pip install`；`pyproject.toml` 中的 `dependencies` 为空、`requirements.txt` 只有注释说明。

节点会出现在右键菜单的 **Prompt Cleaner** 分类下，也会出现在 **Essentials → Basics** 标签页里。

> 节点名的规范语言是**英文**，中文通过官方 i18n（`locales/zh/nodeDefs.json`，由 ComfyUI 的 `/i18n` 路由下发）提供。
> 如果把 ComfyUI 语言设成中文，看到的就是「提示词清洁」。详见文末 FAQ。

## 节点说明

### 1. `Prompt Cleaner`（中文：提示词清洁）— STRING → STRING

| 输入 | 默认 | 说明 |
| --- | --- | --- |
| `text_in` | 未连接 | **常驻可见的 STRING 连线口**（可选） |
| `extra_texts` | 1 个空闲口 | **额外文本口**（`io.Autogrow`）：连上最后一个会自动再补一个，最多 10 个；也可点「＋ 文本输入口」按钮手动加 |
| `text` | 空 | 原始标签，可直接打字；支持逗号分隔、一行一个标签、或两者混合 |
| `bracket_policy` | 仅转义圆括号 | 括号转义策略，见下文（**已收进设置窗口**） |
| `keep_weights` | 开 | 保留显式权重语法 `(tag:1.2)`，只转义真正作为字面内容的括号（**已收进设置窗口**） |
| `underscore_to_space` | 开 | `_` 转空格（**已收进设置窗口**） |
| `dedupe` | 开 | 按标签去重（忽略大小写与首尾空格，保留首次出现）（**已收进设置窗口**） |
| `strip_blacklist` | 开 | 启用黑名单过滤（**已收进设置窗口**） |
| `lowercase` | 关 | 输出标签全部转小写（**已收进设置窗口**） |
| `separator` | 逗号 + 空格 | 标签连接符，可选 **逗号 + 空格**（推荐）/ **仅逗号**（**已收进设置窗口**） |
| `normalize_fullwidth` | 开 | 全角标点/全角空格转半角（**已收进设置窗口**） |
| `blacklist` | 内置默认规则 | 黑名单规则，可随意增删（**已收进设置窗口**） |

**输出**：`cleaned_text` — 单行清洗结果。

> 括号里写着「已收进设置窗口」的那些控件**依然存在**（工作流 JSON 里照旧保存、后端照旧取值），只是不在节点上直接画出来，统一在 **「⚙ 清洁设置」** 弹窗里编辑。详见下文《设置窗口》。

清洗结果会**直接显示在节点上**（文本预览区），不需要另接预览节点。该节点同时被标记为输出节点，所以即使没连下游也会执行并显示结果。

### 2. `Prompt Cleaner (CLIP Text Encode)`（中文：提示词清洁（CLIP 文本编码））

CLIP + STRING → CONDITIONING + STRING

先按上面的规则清洗文本，再把清洗结果交给 CLIP 编码。

| 输出 | 说明 |
| --- | --- |
| `conditioning` | 清洗后文本的编码结果，可直接接采样器 |
| `cleaned_text` | 清洗后的单行文本，便于复用 / 复核 |

同样会把清洗结果显示在节点上。这个节点**不是**输出节点：只有下游真正用到它的输出时才执行，不会白白浪费一次编码。

参数与节点 1 完全一致，只多了一个 `clip` 输入。

## 多路文本输入（自动拼接）

提示词常常散在好几个节点里（角色、画风、质量词……）。本节点可以**同时接多路文本**，接上多少就合并多少：

| 输入 | 说明 |
| --- | --- |
| `text in` | 常驻的第一个 STRING 连线口 |
| 额外口（`text_in_2` … `text_in_10`） | 用 `io.Autogrow` 声明，**连上最后一个会自动再补一个**，也可以点节点上的「＋ 文本输入口」按钮手动加 |
| `提示词文本` 文本框 | 直接打字的那个框，依然有效 |

合并顺序固定为 **`text in` → 额外口（按槽位序号）→ 文本框**，用换行拼成一份文本后**整体清洁**，
所以去重、黑名单、括号转义都作用在合并结果上，**跨来源的重复标签也会被去掉**。

```
text_in        = "sunna_(zenless_zone_zero)"
text_in_2      = "1girl, solo"
text_in_3      = "best_quality"
文本框          = "tagme"          （黑名单里）
────────────────────────────────────────────────
输出            = sunna \(zenless zone zero\), 1girl, solo, best quality
```

* 删口：打开「⚙ 清洁设置」→「文本输入口」，每一行右侧有「移除」（**已连线的口必须先断开**，不会静默剪断你的连线）。
* 加口：节点上的「＋ 文本输入口」按钮、设置窗口里的「＋ 添加」，或者最省事的做法 —— **直接在图上连那个空闲口**。
* 上限 10 个额外口（ComfyUI 的 `Autogrow` 会按声明名逐个展开，全都注册成**可选**输入，不连就是空的，不会报「缺少必填输入」）。

## 设置窗口

节点上只保留「＋ 文本输入口」「⚙ 清洁设置」两个按钮，以及一行**设置摘要**（一眼看清当前开了哪些开关、括号策略与分隔符）。

点「⚙ 清洁设置」（或右键菜单 / 设置摘要附近的同名菜单项）打开弹窗：

| 区块 | 内容 |
| --- | --- |
| 文本输入口 | 列出所有额外口，标出「已连接 / 空闲」，可逐个移除、也可再添加 |
| 清洁选项 | 6 个开关（保留权重 / 下划线转空格 / 去重 / 黑名单过滤 / 转小写 / 全角转半角）+ 2 个下拉（括号转义策略、分隔符） |
| 黑名单 | 一个大的多行编辑框，直接改规则 |

* 弹窗里的改动**点「保存」才生效**，「取消」不会动任何值；「恢复默认」把开关和黑名单恢复成内置默认（即上表里的默认列）。
* 这些控件**本来就在节点上**，只是被「收起来」了（`hidden` + 零高度），所以工作流 JSON、序列化、API 调用、命令行跑 API 格式的工作流**全都不受影响**。
* 开关行右侧的小字是简短说明，完整的解释在各自的 tooltip 里。

## 清洗流水线

顺序固定，不可调换：

0. **合并来源**：`text_in` → 额外文本口（按槽位序号）→ `text` 文本框，用换行拼接成一份待清洗文本
1. **切分**：半角/全角逗号、半角/全角分号、`\n` / `\r\n`
2. **单标签规整**：全角转半角 → 下划线转空格 → 连续空白折叠 → 去首尾空白
3. **黑名单过滤**
4. **括号幂等转义**（先识别并保护权重语法 `(tag:1.2)`；再把已有的 `\(` 还原，最后统一补反斜杠，所以重复执行结果不变）
5. **可选转小写**
6. **去重**（忽略大小写）
7. **拼接**：用分隔符连接，末尾不留多余分隔符

自然语言句子（如 `a girl sitting on a bench`）不含分隔符时会被整体当作一个标签保留，不会被拆散。

## 括号转义策略（重要，请务必读一下）

ComfyUI 源码 `comfy/sd1_clip.py` 里：

```python
def escape_important(text):
    text = text.replace("\\)", "\0\1")
    text = text.replace("\\(", "\0\2")
    return text
```

`escape_important` / `unescape_important` **只识别 `\(` 和 `\)`**，`token_weights` 也只解析圆括号。所以：

| 策略 | 行为 | 建议 |
| --- | --- | --- |
| **仅转义圆括号（默认，推荐）** | `sunna (zenless zone zero)` → `sunna \(zenless zone zero\)`。括号作为字面文本保留，不会被当作权重语法吃掉 | ✅ 用这个 |
| 全部转义 | 额外把 `[ ] { }` 写成 `\[ \] \{ \}` | ⚠️ 见下方警告 |
| 保持原样 | 不做任何转义 | 只在你自己已经在别处处理过括号时使用 |

> ⚠️ **为什么默认不推荐「全部转义」**
>
> `[` `]` `{` `}` 在 ComfyUI 里**本来就不是语法符号**，`\[` `\]` `\{` `\}` **不是**有效转义序列，
> 不会被还原。写成 `\[` 的结果是反斜杠被 Qwen2 分词器当作**字面字符**，等于往 prompt 里注入多余的 `\`。
>
> 该选项保留是为了兼容那些「后续还会把文本丢给别的（A1111 风格）解析器」的流程。

**已验证生效链路**：Anima Base 的文本编码器是 Qwen-3 0.6B（`comfy/text_encoders/anima.py` 中的 `Qwen3_06BModel` 继承 `sd1_clip.SDClipModel`），走的正是上面这条 `escape_important` 路径，所以 `\(` `\)` 对 Anima 确实生效。

### 权重语法会被保留（`keep_weights`，默认开）

转义只针对「字面内容」的括号，**显式权重语法不动**：

| 输入 | 输出 | 说明 |
| --- | --- | --- |
| `(masterpiece:1.2)` | `(masterpiece:1.2)` | 括号内以 `:数字` 结尾 → 判定为权重，原样保留 |
| `(best_quality:1.3)` | `(best quality:1.3)` | 权重保留，括号**内部**的下划线/全角照常规整 |
| `((very_aesthetic:1.15))` | `((very aesthetic:1.15))` | 纯嵌套权重整体保留 |
| `sunna (zenless zone zero)` | `sunna \(zenless zone zero\)` | 不带 `:数字` → 判定为字面内容，转义 |
| `(masterpiece)` | `\(masterpiece\)` | 裸括号没有 `:数字`，无法与「系列名」区分，按字面内容转义 |

判定规则与 ComfyUI `token_weights` 的语义对齐，实现是**单次线性扫描 + 显式栈**，未闭合的 `(` 和多余的 `)` 都会被安全忽略，不会卡住。

> 需要「所有圆括号一律转义」时，把 `keep_weights` 关掉即可，`(masterpiece:1.2)` 会退化成 `\(masterpiece:1.2\)`（权重失效）。

> 裸括号 `(masterpiece)` 一律转义是**刻意**的取舍：ComfyUI 会把任何 `(...)` 当成 ×1.1 的强调并吃掉括号，
> 而 `sunna (zenless zone zero)` 这种角色系列名必须保留括号。要强调请用显式权重 `(tag:1.15)` 写法。

## 黑名单自定义

`blacklist` 输入框默认就是内置规则，直接编辑即可。语法：

```
# 井号开头 = 注释，空行忽略

# 普通标签：整标签匹配（忽略大小写，忽略空格/下划线差异）
watermark
signature
twitter username

# re: 开头 = 正则包含匹配（如需整标签匹配请自己加 ^ $ 锚点）
re:^year\s+\d{4}$
```

* 普通规则用**整标签匹配**而非包含匹配，所以 `signature` 不会误杀 `signature move`。
* 正则写错了不会中断工作流，只会在控制台打印一条警告并跳过该行。
* **清空输入框 = 彻底关闭黑名单过滤**（也可以直接把 `strip_blacklist` 关掉）。

内置默认规则覆盖：`tagme`、`watermark`、`sample watermark`、`signature`、`username`、`twitter username`、`patreon username`、`artist name`、`web address`、`bad id`、`bad source`、`dated`、`logo`、`english text`、`translated`、`check translation`、`speech bubble`、`commentary`、`artist request`、`character request`、`reference request`，以及 `year 20xx` 年份标签。

如果某个默认规则你其实想保留（例如就是要 `commentary`），把那一行删掉即可。

## Anima Base 使用建议

* 只用**逗号 + 空格**连接，不要用句号、分号、冒号 —— 这是默认输出格式
* 标签小写、多词用空格（打开 `lowercase` 可强制统一）
* 权重语法 `(tag:1.2)` 会被原样保留，不会被本节点破坏；但社区规范倾向于「禁权重、只用逗号连接」，是否使用由你决定
* `{tag}` / `[tag]` 这两种 NAI/SD 风格语法在 ComfyUI 里本来就不生效，本节点默认也不会去动它们
* 角色名 + 系列名建议排在通用标签之前，例如 `sunna \(zenless zone zero\), 1girl, drawing bow`
* Anima 的文本编码器是 LLM 类（Qwen-3 0.6B），自然语言描述也能吃；本节点不会把不含分隔符的句子拆散

## 单元测试

两套测试，都能独立运行（退出码 0 表示全过），也都兼容 `pytest`：

```bash
python tests/test_cleaner.py         # 52 例：纯清洗引擎，不依赖 ComfyUI
python tests/test_node_contract.py   # 12 例：节点契约 + 多路输入，需要 ComfyUI 环境
```

### `tests/test_cleaner.py`（纯引擎）

覆盖：用户给的 3 组基准、幂等性、空输入、连续/首尾逗号、大小写去重、黑名单（整标签 / 下划线形态 / 正则 / 非法正则 / 注释）、全角标点、三种括号策略、权重保留（显式 / 嵌套 / 可关闭）、8 层嵌套、以及**未闭合括号不死循环**的回归用例。

### `tests/test_node_contract.py`（节点契约）

这是一个**回归测试**，起因是真实事故：用户在一个「保存于 `text_in` 存在之前」的工作流里运行节点，报
`TypeError: PromptCleanerText.execute() missing 1 required positional argument: 'text_in'`。

根因在 ComfyUI `execution.py`：`input_data_all` **只包含工作流里实际存在的输入键**，不会补默认值。
widget 输入前端总会序列化，所以从不缺失；而 **socket 输入未连接时根本不会出现在 `inputs` 里** ——
因此 socket 输入在 `execute` 签名里**必须带默认值**。

该文件把这个约定固化成断言，防止再次发生：

| 用例 | 作用 |
| --- | --- |
| 每个节点都注册了 node_id 与分类 | 基本 schema 校验 |
| **schema 输入与 execute 参数一一对应** | 漏写参数会被立刻抓出来（就是这次事故） |
| **所有 socket 输入都必须有默认值** | 同上，从签名侧再兜一层 |
| 不传任何输入也能执行 | 最老式的 API 工作流也不崩 |
| 缺输入的 None 不会静默关掉开关 | 防 `bool(None) == False` 把去重/黑名单悄悄关掉 |
| 旧工作流缺少 socket 输入仍可运行 | 精确复现事故场景 |
| 额外文本插槽会展开成可选输入 | 直接调 ComfyUI 的 `get_finalized_class_inputs`，锁住「前端插槽名 = `extra_texts.text_in_N`」这套约定 |
| 多来源文本按 首口 → 额外口 → 文本框 的顺序合并 | 顺序、跨来源去重 |
| 额外文本插槽的脏值不会让节点崩溃 | 非字典 / 非字符串（`None`、占位对象）都被安全忽略 |
| 两个节点都在中文语言包里有翻译 | i18n 完整性 |

在没有 ComfyUI 的纯 Python 环境里，这个文件会自动打印 `[skip]` 并跳过，不会报错。

## 目录结构

```
Comfyui-Promote-Cleaner/
├── __init__.py                          # V3 入口：comfy_entrypoint -> ComfyExtension
├── nodes.py                             # 两个 V3 节点定义（参数装配 + 预览 + CLIP 编码）
├── prompt_cleaner/                      # 纯 Python 清洗引擎（不 import ComfyUI）
│   ├── __init__.py                      # 对外导出
│   ├── config.py                        # CleanOptions / BracketPolicy
│   ├── blacklist.py                     # 默认黑名单 + 规则解析
│   └── cleaner.py                       # 切分 -> 规整 -> 过滤 -> 转义 -> 去重 -> 拼接
├── web/
│   └── js/prompt_cleaner.js             # 前端扩展：大按钮 + 设置弹窗 + 文本输入口增减
├── locales/
│   └── zh/nodeDefs.json                 # 官方 i18n：节点名/描述/输入名/提示 的中文
├── docs/
│   ├── PromoteCleaner_Text.md           # 帮助页（文件名必须等于 node_id）
│   └── PromoteCleaner_ClipEncode.md
├── tests/
│   ├── test_cleaner.py                  # 纯引擎单测（不依赖 ComfyUI）
│   └── test_node_contract.py            # 节点契约回归测试（需要 ComfyUI）
├── pyproject.toml                       # 含 [tool.comfy] 注册表元数据
├── requirements.txt                     # 无第三方依赖
├── LICENSE                              # MIT
├── .gitignore
└── README.md
```

## 常见问题

**Q：为什么 `_` 全变成空格了，`score_9` 也变成 `score 9`？**
A：默认开启「下划线转空格」。Anima 用的就是空格形态；如果你确实需要保留下划线（例如某些带 `score_9` 的美学标签），把 `underscore_to_space` 关掉即可。

**Q：输出末尾没有逗号，可以加吗？**
A：不加。逗号只是标签之间的分隔符，末尾多一个逗号没有语义。如果你要拼接别的文本，直接连就行。

**Q：`text_in` / 额外口 / `text` 文本框是什么关系？**
A：**不是二选一**，也不是「按需选一个」——**接上几个就用几个**，按 `text_in` → 额外口（槽位序号）→ 文本框的顺序合并后一起清洁。
所以去重、黑名单、括号转义都作用在合并后的整份文本上，跨来源的重复标签也会被去掉。

| `text_in` | 额外口 | `text` | 实际清洁的内容 |
| --- | --- | --- | --- |
| 未连接 | 无 | `1girl, solo` | `1girl, solo` |
| `sunna_(zenless_zone_zero)` | 无 | 空 | `sunna \(zenless zone zero\)` |
| `sunna_(zenless_zone_zero)` | `1_girl` | 空 | `sunna \(zenless zone zero\), 1 girl` |
| `sunna_(zenless_zone_zero)` | `1_girl` | `best_quality` | `sunna \(zenless zone zero\), 1 girl, best quality` |
| `tagme`（黑名单开） | `watermark` | `logo` | 空（三个来源都被过滤） |

文本框默认是空的（示例文本挪到了占位提示里），所以只连线不填框时不会混进无关内容。

**Q：为什么要专门加一个 `text_in`？widget 不能连线吗？**
A：能。ComfyUI 的 widget **本身支持连线**（鼠标悬停到控件左边缘会冒出连接点）。但那个连接点要悬停才显形，不够直观，所以额外加了 `text_in` 这个**常驻可见**的插槽（`force_input=True`，只作为连线口，不占文本框）。两个都能用。

**Q：开关去哪了？我只看到两个按钮。**
A：`bracket_policy` / `keep_weights` / … / `blacklist` 这 9 个控件**没有删除**，只是隐藏了（`hidden` + 高度压成 0），统一放进「⚙ 清洁设置」弹窗。
好处是节点变矮变干净，而工作流 JSON、`widgets_values`、API 调用、命令行跑 API 格式工作流**一切照旧** —— 后端取到的还是这些同名参数。

**Q：为什么我加了口又自己多出来一个？删掉的口会回来吗？**
A：额外口是 ComfyUI 的 `Autogrow`：**连上最后一个空闲口时会自动再补一个**，方便你随手接第三、第四路文本，最多到 `text_in_10`。
用「移除」删掉的口不会自己回来；但如果删掉的是「最后一个被连上时新生成的那个」，下次再连最后一口时又会出现一个 —— 这是框架行为，重新移除即可。

**Q：设置窗口里的开关能显示中文吗？**
A：能。这些开关刻意**不使用** `label_on` / `label_off`（官方 i18n 不支持翻译这两个字段），而是让控件标签回退到输入名，于是可以走官方 i18n。
把 ComfyUI 语言设为中文（设置 → Comfy → Locale → 中文，或浏览器语言为中文），节点名、tooltip 与设置窗口的文案都会变成 `locales/zh/nodeDefs.json` 里的中文：下划线转空格 / 去重 / 黑名单过滤 / 转小写 / 保留权重语法 / 全角转半角。
注意：汉化类插件（如 `ComfyUI-Chinese-Translation`）只认识它自己收录过的节点，**不认识第三方节点**，所以不能指望它来翻译。

**Q：下拉框的选项（括号转义策略 / 分隔符）是中文，能变英文吗？**
A：不能，这是有意为之。下拉选项是**参数值**（会写进工作流 JSON），不是可翻译的界面文案，官方 i18n 也不覆盖它。所以直接写成中文的可读名称，避免出现「两个看起来一模一样的逗号」这种歧义（旧版本就是那样，现已修掉）。英文用户可看 tooltip 里的解释。

**Q：我以前存的工作流里 `separator` 是 `", "`，会坏吗？**
A：不会。装配参数时同时兼容新的展示项（`逗号 + 空格` / `仅逗号`）和旧的原始分隔符（`", "` / `","`），旧的直接照用。

**Q：节点加载失败 / 看不到节点？**
A：本插件需要 ComfyUI `>= 0.3.60`（V3 节点 API）。0.35.0 已实测通过。若版本过老，请升级 ComfyUI。

**Q：节点上看不到「＋ 文本输入口」「⚙ 清洁设置」按钮？**
A：这两个按钮由前端扩展（`web/js/prompt_cleaner.js`，通过 `WEB_DIRECTORY` 注册）添加。如果没出现，先看浏览器控制台有没有报错，并**强制刷新页面**（Ctrl+F5）清掉旧 JS 缓存 —— 自定义节点的前端文件是会被浏览器缓存的。
即使前端扩展没加载，**后端节点依然完整可用**（多路输入口照样能连、能清洁），只是少了这两个按钮和设置弹窗。

**Q：会不会打印我的提示词内容？**
A：不会写日志。清洗结果只会通过 ComfyUI 的节点预览通道发给你自己的界面看，日志里不记录任何 prompt 内容。

**Q：发布到 ComfyUI Registry 需要改什么？**
A：`pyproject.toml` 里 `[tool.comfy]` 的 `PublisherId` 已经写成 `L134283`（= 本仓库的 GitHub 用户名）。如果你 fork 之后要自己发布，把它换成**你的** GitHub 用户名，然后 `comfy node publish`。

## 开源许可

[MIT](LICENSE) —— 随便用、随便改、随便再发布，保留版权声明即可。

欢迎提 [Issue](https://github.com/L134283/comfyui-promote-cleaner/issues) 或 PR。
