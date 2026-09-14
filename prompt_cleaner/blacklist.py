"""黑名单过滤：内置默认规则 + 用户在节点上自定义的规则。

规则语法（每行一条）：

* 空行、``#`` 开头的行为注释，忽略。
* ``re:`` 前缀 = 正则规则，做**包含匹配**（``re.search``，忽略大小写）。
  需要「整标签匹配」请自行加锚点，例如 ``re:^year\\s+\\d{4}$``。
* 其余行 = 普通标签，做**整标签匹配**（忽略大小写、忽略空格/下划线差异）。

普通标签采用「整标签匹配」而不是包含匹配，是为了避免误杀：
``signature`` 不会把 ``signature move`` 一起干掉。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

#: 默认黑名单。节点上的 ``blacklist`` 输入框默认就是这段文本，用户可随意增删。
DEFAULT_BLACKLIST = """\
# ===== Prompt Cleaner 默认黑名单 =====
# 每行一条规则；# 开头为注释；清空本框 = 关闭黑名单过滤。
# 普通标签：忽略大小写、忽略空格/下划线差异，做「整标签」匹配。
# 正则规则：以 re: 开头，做包含匹配（如需整标签匹配请用 ^...$ 锚点）。

# --- Danbooru meta / 水印 / 署名类 ---
tagme
watermark
sample watermark
signature
username
twitter username
patreon username
artist name
web address
bad id
bad source
dated
logo

# --- 纯文字 / 对话框 / 翻译标注类 ---
english text
translated
check translation
speech bubble
commentary

# --- 请求类站位标签（对出图无意义） ---
artist request
character request
reference request

# --- 年份标签，如 year 2024 ---
re:^year\\s+\\d{4}$
"""


@dataclass(frozen=True)
class BlacklistSpec:
    """编译后的黑名单：整标签集合 + 正则列表。"""

    exact: frozenset[str]
    patterns: tuple[re.Pattern[str], ...]

    def __bool__(self) -> bool:
        return bool(self.exact) or bool(self.patterns)


#: 空黑名单，用于关闭过滤时短路。
EMPTY_BLACKLIST = BlacklistSpec(frozenset(), ())


def parse_blacklist(text: str | None) -> BlacklistSpec:
    """把用户文本解析成 ``BlacklistSpec``；非法正则会被跳过并记录警告，不影响主流程。"""
    exact: set[str] = set()
    patterns: list[re.Pattern[str]] = []

    for line in (text or "").splitlines():
        rule = line.strip()
        if not rule or rule.startswith("#"):
            continue

        if rule[:3].lower() == "re:":
            expression = rule[3:].strip()
            if not expression:
                continue
            try:
                patterns.append(re.compile(expression, re.IGNORECASE))
            except re.error as exc:
                LOGGER.warning("[PromptCleaner] 忽略非法黑名单正则 %r: %s", expression, exc)
            continue

        low = rule.lower()
        exact.add(low)
        # 同时登记下划线形态，这样无论用户是否开启「下划线转空格」都能命中。
        exact.add(low.replace(" ", "_"))

    return BlacklistSpec(frozenset(exact), tuple(patterns))


def is_blacklisted(tag: str, spec: BlacklistSpec) -> bool:
    """判断单个标签是否命中黑名单。"""
    if not spec:
        return False

    low = tag.lower()
    keys = (low, low.replace(" ", "_"), low.replace("_", " "))

    if spec.exact.intersection(keys):
        return True

    for pattern in spec.patterns:
        for key in keys:
            if pattern.search(key):
                return True

    return False
