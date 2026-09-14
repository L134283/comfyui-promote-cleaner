# 贡献 / 开发 / 发布

面向**维护者与贡献者**的说明。普通用户只需要看 [README](README.md)。

## 本地开发

本插件零第三方依赖（只用 Python 标准库），也不需要 `pip install` 任何东西 —— 把仓库放进
`ComfyUI/custom_nodes/` 重启即可。模块划分：

| 路径 | 职责 |
| --- | --- |
| `nodes.py` | 两个 V3 节点的定义：schema、参数装配、结果预览、CLIP 编码 |
| `prompt_cleaner/` | 纯 Python 清洗引擎，**不 import ComfyUI**，可以脱离 ComfyUI 单测 |
| `web/js/prompt_cleaner.js` | 前端扩展：大按钮、设置弹窗、文本输入口的增减 |
| `locales/zh/nodeDefs.json` | 官方 i18n（节点名 / 描述 / 输入名 / tooltip） |

> 前端 JS 会被浏览器缓存：改完 `web/js/*.js` 之后要 **Ctrl+F5** 强刷才看得到效果。

## 跑测试

三套测试都能独立运行（退出码 0 = 全过），也都兼容 `pytest`：

```bash
python tests/test_cleaner.py            # 50 例：纯清洗引擎，不依赖 ComfyUI
python tests/test_frontend_contract.py  #  5 例：前后端命名契约，不依赖 ComfyUI
python tests/test_node_contract.py      # 10 例：节点契约 + 多路输入，需要 ComfyUI 环境
```

### `tests/test_cleaner.py`（纯引擎）

覆盖：用户给的 3 组基准、幂等性、空输入、连续/首尾逗号、大小写去重、黑名单（整标签 / 下划线形态 / 正则 / 非法正则 / 注释）、全角标点、三种括号策略、权重保留（显式 / 嵌套 / 可关闭）、8 层嵌套，以及**未闭合括号不死循环**的回归用例。

### `tests/test_frontend_contract.py`（前后端契约）

`web/js/prompt_cleaner.js` 里硬编码了几份「必须与后端对齐」的清单（负责哪些节点、要收进弹窗的控件名、额外口插槽名）。这些东西**写错不报错，只会静默失效**，所以用纯文本解析把它们钉住：

| 用例 | 作用 |
| --- | --- |
| 前端 `NODE_TYPES` = 后端 `node_id` | 节点改名后前端不会「失联」 |
| 设置弹窗里的控件名都真实存在 | 防「控件没收起来 / 弹窗改了个不存在的名字」 |
| 开关与下拉清单都在 `OPTION_WIDGETS` 里 | 防出现两套 UI（一个收起来、一个还留在节点上） |
| 额外文本插槽名与后端 `Autogrow` 声明一致 | 前端手加的口后端必须认识 |
| 节点帮助页放在 `WEB_DIRECTORY` 里 | 曾经踩过的坑：放包根的 `docs/` 前端取不到 |

### `tests/test_node_contract.py`（节点契约）

这是一个**回归测试**，起因是真实事故：用户在一个「保存于 `text_in` 存在之前」的工作流里运行节点，报
`TypeError: PromptCleanerText.execute() missing 1 required positional argument: 'text_in'`。

根因在 ComfyUI `execution.py`：`input_data_all` **只包含工作流里实际存在的输入键**，不会补默认值。
widget 输入前端总会序列化，所以从不缺失；而 **socket 输入未连接时根本不会出现在 `inputs` 里** ——
因此 socket 输入在 `execute` 签名里**必须带默认值**。该文件把这个约定固化成断言：

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

## 改代码时的几条硬规矩

1. **socket 输入必须给默认值**：`execute` 签名里凡是「未连接时不会出现在 `inputs` 里」的参数，都要写 `=None` 并回落到引擎默认值（用 `bool(None)` 判断会把开关静默关掉，参考 `_make_options` 里的 `flag()`）。
2. **改了输入 id 要同步前端**：`OPTION_WIDGETS`（要收进弹窗的控件名）、`NODE_TYPES`、额外口插槽名，改错只会静默失效 —— 契约测试会拦，但记得改。
3. **新增开关要补 i18n**：`locales/zh/nodeDefs.json` 里补 `inputs.<id>.name` / `tooltip`，契约测试会检查。
4. **节点帮助页必须在 `web/docs/<node_id>.md`**（`WEB_DIRECTORY` 里面）。放包根的 `docs/` 前端取不到。
5. **不要给 Boolean 输入设置 `label_on` / `label_off`**：官方 i18n 不覆盖这两个字段，一旦设置就再也翻译不了。
6. **括号 / 权重的行为改动要谨慎**：`(tag:1.2)` 的判定对齐 `comfy/sd1_clip.py` 的 `token_weights` 语义，改错了会破坏别人的提示词权重。

## CI（GitHub Actions）

| 工作流 | 触发 | 做什么 |
| --- | --- | --- |
| `.github/workflows/tests.yml` | push / PR | Python 3.10 与 3.12 下跑 `test_cleaner.py` + `test_frontend_contract.py` + `compileall`；另起一个 job 用 Node 校验前端扩展的语法 |
| `.github/workflows/publish_action.yml` | push 改动 `pyproject.toml` / 手动 | 调用官方 `Comfy-Org/publish-node-action` 发布到 Comfy Registry |

CI 里**不跑** `test_node_contract.py`（它要 `import comfy_api`，也就是要一套 ComfyUI 环境），该文件在无 ComfyUI 的机器上会自动跳过；本地装了 ComfyUI 时请手动跑它。

## 发布到 Comfy Registry

一次性准备：

1. 在 https://registry.comfy.org 创建 **Publisher**，ID 取 `yuinya`（必须与 `pyproject.toml` 里的 `PublisherId` 一致；**ID 创建后不可修改**）。
2. 在该 publisher 下创建 **API Key**（只显示一次，务必先存好）。
3. 在 GitHub 仓库 `Settings → Secrets and variables → Actions` 添加 Secret：名字 **`REGISTRY_ACCESS_TOKEN`**，值填上面那个 API Key。

之后每次发版：

```bash
# 改 pyproject.toml 里的 version（同一个版本号不能重复发布），然后 push
git commit -am "Bump version to 1.1.1" && git push
```

`publish_action.yml` 会自动把它发到 Registry。**没配 Secret 之前不会报错**，只会打印一条 warning 然后跳过。

发布后的节点页面：https://registry.comfy.org/nodes/comfyui-promote-cleaner
（URL 是 `/nodes/<节点ID>`，**不是** `/<发布者>/<节点>`；包下载地址形如 `https://cdn.comfy.org/yuinya/comfyui-promote-cleaner/<版本>/node.zip`。）

也可以在本地发（需要 `pip install comfy-cli`）：

```bash
comfy node publish     # 提示时粘贴 API Key
```

> Windows 提醒：官方文档明确指出 `Ctrl+V` 粘贴 API Key 会多带一个 `\x16` 字符导致认证失败，请用**鼠标右键粘贴**。

### 元数据里容易被拒的几处（官方规范）

| 字段 | 要求 |
| --- | --- |
| `license` | **只能**写成 `{ file = "LICENSE" }` 或 `{ text = "MIT License" }`；裸字符串（`license = "MIT"`）会被拒 |
| `[project.urls] Repository` | 必填 |
| `[project] name` | 全局唯一、<100 字符、只能字母数字 `-` `_` `.`、不能有连续特殊字符、不能以数字开头；官方还建议**不要包含 "ComfyUI"** |
| `version` | 必须 `X.Y.Z` 语义化版本，**同一个版本号不能重复发布** |
| `PublisherId` | 必须与 Registry 上的 Publisher ID 完全一致 |
| `Icon` / `Banner` | 可选；Icon ≤400×400 且正方形，Banner 比例 21:9 |

首次发布的版本状态可能是 `NodeVersionStatusPending`（审核/处理中），转成 `Active` 之后 ComfyUI-Manager 才能正常显示最新版本。

## 提 PR

* 提交前请跑一遍上面三套测试（有 ComfyUI 环境时把 `test_node_contract.py` 也跑上）。
* 顺手改一下 `README.md` 里受影响的说明（输入表、FAQ）会省很多沟通。
* 发版与元数据相关的改动（`pyproject.toml`）请单独一个提交，避免把普通改动和发版混在一起。
