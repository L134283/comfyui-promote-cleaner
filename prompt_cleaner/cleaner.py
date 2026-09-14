"""提示词清洁核心引擎。

本模块**不依赖 ComfyUI**，可脱离 ComfyUI 单独运行与单元测试。

流水线顺序（不可调换）：

1. 切分：半角/全角逗号、半角/全角分号、换行
2. 单标签规整：全角转半角 -> 下划线转空格 -> 空白折叠 -> 去首尾空白
3. 黑名单过滤
4. 括号幂等转义（先把已有 ``\\(`` 还原，再统一补反斜杠）
5. 可选转小写
6. 去重（忽略大小写，保留首次出现）
7. 用分隔符拼接
"""

from __future__ import annotations

import re

from .blacklist import (
    EMPTY_BLACKLIST,
    BlacklistSpec,
    is_blacklisted,
    parse_blacklist,
)
from .config import DEFAULT_SEPARATOR, BracketPolicy, CleanOptions

#: 输入切分：半角/全角逗号、半角/全角分号、\r\n / \n / \r。
_SPLIT_RE = re.compile(r"[,，;；\r\n]+")

#: 连续空白折叠为单个空格（全角空格 \u3000 一并处理）。
_WS_RE = re.compile(r"[ \t\f\v\u3000]+")

#: 输入中已存在的反斜杠转义，用于「先还原再统一转义」，保证重复执行结果一致。
_ESCAPED_RE = re.compile(r"\\([()\[\]{}])")

#: 按策略预编译的转义正则（模块导入期一次编译，避免执行期重复编译）。
_ESCAPE_RE: dict[BracketPolicy, re.Pattern[str]] = {
    BracketPolicy.PARENS_ONLY: re.compile(r"([()])"),
    BracketPolicy.ESCAPE_ALL: re.compile(r"([()\[\]{}])"),
}

#: 显式权重语法：括号内容以 ``:数字`` 结尾，例如 ``(masterpiece:1.2)`` / ``(best quality: 1.3)``。
_WEIGHT_SUFFIX_RE = re.compile(r":\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*$")

#: 全角 -> 半角映射。
_FULLWIDTH_TABLE = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "，": ",",
        "；": ";",
        "：": ":",
        "＿": "_",
        "　": " ",
        "［": "[",
        "］": "]",
        "｛": "{",
        "｝": "}",
    }
)


def split_tags(text: str) -> list[str]:
    """按逗号 / 分号 / 换行切分原始文本。"""
    if not text:
        return []
    return _SPLIT_RE.split(text)


def normalize_tag(tag: str, options: CleanOptions) -> str:
    """规整单个标签：全角转半角、下划线转空格、空白折叠、去首尾空白。"""
    if options.normalize_fullwidth:
        tag = tag.translate(_FULLWIDTH_TABLE)
    if options.underscore_to_space:
        tag = tag.replace("_", " ")
    tag = _WS_RE.sub(" ", tag)
    return tag.strip()


def normalize_escapes(tag: str) -> str:
    """把输入中已存在的 ``\\(`` ``\\)`` ``\\[`` ``\\]`` ``\\{`` ``\\}`` 还原为字面括号。

    这样「已经清洗过的文本」再次清洗不会变成 ``\\\\(``，保证幂等。
    """
    return _ESCAPED_RE.sub(r"\1", tag)


def weight_spans(tag: str) -> list[tuple[int, int]]:
    """找出标签中所有「应当保留为权重语法」的括号组区间。

    判定规则（与 ComfyUI ``comfy/sd1_clip.py`` 的 ``token_weights`` 语义对齐）：

    * ``(masterpiece:1.2)`` —— 括号内容以 ``:数字`` 结尾，是显式权重；
    * ``((masterpiece:1.2))`` —— 去掉子权重组后没有别的字面内容，属于纯嵌套权重。

    注意 ``(zenless zone zero)`` 这种**不带** ``:数字`` 的括号会被判定为字面内容，
    仍按策略转义 —— 否则就没法区分「角色系列名」和「淡淡的强调」了。

    实现说明：单次线性扫描 + 显式栈，**不使用递归回溯**。
    未闭合的 ``(`` 与多余的 ``)`` 都会被安全忽略，绝不会卡住。
    """
    # 栈内每层记录：括号起始下标、该层直接字面内容（已剔除权重子组）、是否存在权重子组
    stack: list[dict] = []
    spans: list[tuple[int, int]] = []

    for index, char in enumerate(tag):
        if char == "(":
            stack.append({"open": index, "literal": [], "weight_child": False})
            continue

        if char == ")":
            if not stack:
                continue  # 多余的右括号，忽略
            frame = stack.pop()
            literal = "".join(frame["literal"])
            is_weight = bool(_WEIGHT_SUFFIX_RE.search(literal)) or (
                frame["weight_child"] and not literal.strip()
            )
            if is_weight:
                spans.append((frame["open"], index + 1))
                # 权重组整体不计入父层的字面内容，但要让父层知道「我有个权重子组」
                if stack:
                    stack[-1]["weight_child"] = True
            elif stack:
                # 非权重组的内容原样回填父层，供父层做后缀判定
                stack[-1]["literal"].append("(" + literal + ")")
            continue

        if stack:
            stack[-1]["literal"].append(char)

    return sorted(set(spans))


def escape_brackets(
    tag: str,
    policy: BracketPolicy | str,
    keep_weights: bool = True,
) -> str:
    """按策略给括号补反斜杠。``保持原样`` 时不改动任何字符。

    Args:
        tag: 规整后的单个标签。
        policy: 括号转义策略。
        keep_weights: 为 ``True`` 时，显式权重语法 ``(tag:1.2)`` 的括号**不转义**，
            交给 ComfyUI 正常解析权重；其余括号照常转义。
    """
    resolved = BracketPolicy.coerce(policy)
    if resolved is BracketPolicy.NONE:
        return tag

    tag = normalize_escapes(tag)
    protected: set[int] = set()
    if keep_weights:
        for span_start, span_end in weight_spans(tag):
            protected.update(range(span_start, span_end))

    def _replace(match: re.Match[str]) -> str:
        if match.start() in protected:
            return match.group(0)
        return "\\" + match.group(0)

    return _ESCAPE_RE[resolved].sub(_replace, tag)


def clean_prompt(text: str, options: CleanOptions | None = None) -> str:
    """把原始提示词清洗成规范格式。

    Args:
        text: 用户粘贴的原始文本，可以是逗号串、一行一个标签或两者混合。
        options: 清洗参数，``None`` 时使用默认参数。

    Returns:
        用 ``options.separator`` 连接的一行结果；输入为空时返回空串（不抛异常）。
    """
    opts = options if options is not None else CleanOptions()
    if not text:
        return ""

    separator = opts.separator or DEFAULT_SEPARATOR

    spec: BlacklistSpec = (
        parse_blacklist(opts.blacklist) if opts.strip_blacklist else EMPTY_BLACKLIST
    )

    seen: set[str] = set()
    kept: list[str] = []

    for raw in split_tags(text):
        tag = normalize_tag(raw, opts)
        if not tag:
            continue

        if opts.strip_blacklist and is_blacklisted(tag, spec):
            continue

        tag = escape_brackets(tag, opts.bracket_policy, keep_weights=opts.keep_weights)

        if opts.lowercase:
            tag = tag.lower()

        if opts.dedupe:
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)

        kept.append(tag)

    return separator.join(kept)
