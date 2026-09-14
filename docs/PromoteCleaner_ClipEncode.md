# Prompt Cleaner (CLIP Text Encode) / 提示词清洁（CLIP 文本编码）

先按 Prompt Cleaner 的规则清洗文本，再把**清洗后**的结果交给 CLIP 编码。

一路输出 `CONDITIONING` 可直接接采样器，另一路输出清洗后的文本便于复用或复核 —— 一个节点顶「清洁 + 编码」两步，省一条连线。

清洗结果同时会显示在节点上。

## 输入

| 输入 | 说明 |
| --- | --- |
| `clip` | CLIP / 文本编码器（Anima 用 `qwen_3_06b_base.safetensors`） |
| `text_in` | 常驻可见的 STRING 连线口，上游来的提示词会被清洁 |
| `extra_texts` | 额外文本口：连上最后一个会自动再补一个（最多 10 个），也可点「＋ 文本输入口」手动加 |
| `text` | 原始标签，可直接打字。支持逗号分隔、一行一个标签、或两者混合 |
| `bracket_policy` | 括号转义策略（**已收进设置窗口**） |
| `keep_weights` | 保留显式权重语法 `(tag:1.2)`（**已收进设置窗口**） |
| `underscore_to_space` | `_` 转空格（**已收进设置窗口**） |
| `dedupe` | 按标签去重（**已收进设置窗口**） |
| `strip_blacklist` | 启用黑名单过滤（**已收进设置窗口**） |
| `lowercase` | 输出标签全部转小写（**已收进设置窗口**） |
| `separator` | 标签连接符，默认 `, `（**已收进设置窗口**） |
| `normalize_fullwidth` | 全角转半角（**已收进设置窗口**） |
| `blacklist` | 黑名单规则（**已收进设置窗口**） |

多路文本按 **`text in` → 额外口（槽位序号）→ 文本框** 的顺序拼接成一份提示词，清洗后再编码；设置项统一在「⚙ 清洁设置」弹窗里编辑（点「保存」才生效）。

## 输出

| 输出 | 说明 |
| --- | --- |
| `conditioning` | 清洗后文本的编码结果，可直接接采样器 |
| `cleaned_text` | 清洗后的单行提示词，便于复用或复核 |

## 与原生 CLIP Text Encode 的关系

等价于 `Prompt Cleaner → CLIP Text Encode`，但内部是**先清洗再 tokenize**，不会把没洗过的原文喂给编码器。

`clip` 为空时抛出的错误与原生 `CLIP Text Encode` 完全一致。

## 注意

- 该节点**不是**输出节点：只有当下游真正用到它的输出时才会执行，不会白白浪费一次编码。
- 关于括号与权重的行为，与 `Prompt Cleaner` 完全一致，见该节点的帮助页。
