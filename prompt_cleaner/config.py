"""Prompt Cleaner 的配置契约：括号策略与清洗参数。

这里是节点参数、清洗引擎、单元测试之间的公共契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .blacklist import DEFAULT_BLACKLIST


class BracketPolicy(str, Enum):
    """括号处理策略。

    技术背景（已核对 ComfyUI 源码 ``comfy/sd1_clip.py``）：

    * ``escape_important`` / ``unescape_important`` 只识别 ``\\(`` 与 ``\\)``，
      ``token_weights`` 也只解析圆括号。所以只有 ``\\(`` ``\\)`` 是**真正生效**的转义，
      能让括号作为字面文本保留、不被当成权重语法吃掉。
    * ``[ ] { }`` 在 ComfyUI 里**不是**语法符号，写成 ``\\[`` 不会被还原，
      反斜杠会被 Qwen2 分词器当作字面字符，等于往 prompt 里注入多余的 ``\\``。
    """

    PARENS_ONLY = "仅转义圆括号（推荐）"
    ESCAPE_ALL = "全部转义（圆括号+方括号+花括号）"
    NONE = "保持原样（不转义）"

    @classmethod
    def coerce(cls, value: "BracketPolicy | str | None") -> "BracketPolicy":
        """把任意输入（枚举 / 中文选项值 / 枚举名 / None）安全转成策略，未知值回退默认。"""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            for member in cls:
                if value in (member.value, member.name):
                    return member
        return DEFAULT_BRACKET_POLICY


#: 默认括号策略：只转义圆括号（用户已确认）。
DEFAULT_BRACKET_POLICY = BracketPolicy.PARENS_ONLY

#: 分隔符下拉框：展示项 -> 实际使用的分隔符。
#:
#: 展示项会作为参数值写进工作流，且官方 i18n 不覆盖下拉选项，
#: 所以直接用可读的名称，避免出现两个「看起来一样」的逗号选项。
SEPARATOR_CHOICES: tuple[str, ...] = ("逗号 + 空格", "仅逗号")
SEPARATOR_VALUES: dict[str, str] = {"逗号 + 空格": ", ", "仅逗号": ","}

#: 默认的分隔符展示项。
DEFAULT_SEPARATOR_CHOICE = SEPARATOR_CHOICES[0]

#: 默认输出分隔符：逗号 + 空格。
DEFAULT_SEPARATOR = ", "


@dataclass
class CleanOptions:
    """一次清洗的全部可调参数。"""

    #: ``_`` 转空格，例如 ``drawing_bow`` -> ``drawing bow``。
    underscore_to_space: bool = True
    #: 括号处理策略。
    bracket_policy: BracketPolicy = DEFAULT_BRACKET_POLICY
    #: 保留显式权重语法 ``(tag:1.2)``，只转义真正作为字面内容的括号。
    keep_weights: bool = True
    #: 按标签去重（忽略大小写与首尾空格），只保留第一次出现。
    dedupe: bool = True
    #: 输出标签统一转小写（符合 Anima 社区规范，默认关闭）。
    lowercase: bool = False
    #: 是否启用黑名单过滤。
    strip_blacklist: bool = True
    #: 是否把全角标点/全角空格规整为半角。
    normalize_fullwidth: bool = True
    #: 标签之间的连接符。
    separator: str = DEFAULT_SEPARATOR
    #: 黑名单规则文本，默认使用内置规则。
    blacklist: str = DEFAULT_BLACKLIST
