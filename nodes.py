"""Prompt Cleaner node definitions (ComfyUI V3 node API).

用户可见文案一律用英文，中文通过 ``locales/zh/nodeDefs.json`` 走官方 i18n
（由 ComfyUI 的 ``app/custom_node_manager.py`` 的 ``/i18n`` 路由下发）。
"""

from __future__ import annotations

import logging

from comfy_api.latest import io, ui

from .prompt_cleaner import (
    DEFAULT_BLACKLIST,
    DEFAULT_BRACKET_POLICY,
    DEFAULT_SEPARATOR,
    DEFAULT_SEPARATOR_CHOICE,
    SEPARATOR_CHOICES,
    SEPARATOR_VALUES,
    BracketPolicy,
    CleanOptions,
    clean_prompt,
)

LOGGER = logging.getLogger(__name__)

CATEGORY = "Prompt Cleaner"
ESSENTIALS_CATEGORY = "Basics"

#: 额外文本插槽的名字（``text_in`` 之后的第 2 ~ 第 10 个）。
#:
#: 这里用 :class:`io.Autogrow` 的 ``TemplateNames`` 模式，而不是手工在前端插拔插槽：
#: ComfyUI 会把 ``names`` 里的每一项都展开成一个**合法的可选输入**，
#: 名字形如 ``extra_texts.text_in_2``（前端也正是按这个格式生成插槽）。
#: 所以「多连一个口」在前端点一下就行，后端校验不需要任何特例；
#: 用户还可以直接在设置窗口里增减插槽（见 ``web/js/prompt_cleaner.js``）。
EXTRA_TEXT_SLOT_NAMES: tuple[str, ...] = tuple(
    f"text_in_{index}" for index in range(2, 11)
)

_EXAMPLE_TEXT = (
    "drawing_bow, sunna_(zenless_zone_zero), (masterpiece:1.3), "
    "best_quality, drawing_bow, tagme"
)

_BRACKET_TOOLTIP = (
    "Bracket escaping policy.\n"
    "- Escaped parentheses only (recommended): sunna (zenless zone zero) -> "
    "sunna \\(zenless zone zero\\). In ComfyUI only \\( \\) is a real escape "
    "sequence (see escape_important in comfy/sd1_clip.py).\n"
    "- Escape everything: also backslash-escape square and curly brackets. "
    "Note that [ ] { } are NOT syntax in ComfyUI, so \\[ \\] \\{ \\} is never "
    "unescaped and the backslash ends up as a literal character for the "
    "Qwen2 tokenizer.\n"
    "- Leave as is: no escaping at all.\n"
    "Explicit weights such as (tag:1.2) are handled by the separate "
    "'keep_weights' toggle, not by this policy."
)

_KEEP_WEIGHTS_TOOLTIP = (
    "Preserve explicit weight syntax:\n"
    "masterpiece, (best_quality:1.3) -> masterpiece, (best quality:1.3)\n"
    "A bracket group ending in :number is treated as a weight and kept as is so "
    "ComfyUI can parse it normally; all other brackets (such as the character "
    "series in 'sunna (zenless zone zero)') are escaped as usual.\n"
    "Nested weights such as ((tag:1.2)) are preserved too.\n"
    "Turn this off to escape every parenthesis, which would degrade "
    "(masterpiece:1.2) into \\(masterpiece:1.2\\) and drop the weight."
)

_BLACKLIST_TOOLTIP = (
    "Blacklist rules, one per line:\n"
    "- blank lines, and lines starting with #, are comments;\n"
    "- plain text = whole-tag match (case-insensitive, spaces and underscores "
    "treated as equal), e.g. watermark;\n"
    "- re: prefix = regular expression, partial match, e.g. re:^year\\s+\\d{4}$.\n"
    "Clear this box to disable blacklist filtering entirely."
)


_EXTRA_TEXTS_TOOLTIP = (
    "Extra text inputs.\n"
    "- Connect a socket to make the next one appear (up to 10 extra sockets);\n"
    "- or use the '+ text input' button on the node / the settings window to add "
    "or remove sockets by hand.\n"
    "Everything that is connected is concatenated in order (text in -> extra "
    "inputs -> prompt text box) and cleaned as one prompt, so dedupe and blacklist "
    "also work across sources."
)


def _build_text_inputs() -> list:
    """构造文本输入：常驻可见的首个连线口 + 可自由增减的额外连线口 + 文本框。

    文本节点原本只有 widget，插槽要悬停才出现，用起来不够直观，
    所以额外提供一个 ``text_in`` 常驻插槽（``force_input=True`` 让它只作为连线口存在）。

    首口与文本框**不是二选一**：``text_in`` 连上后，文本框里的内容依然有效，
    会按「首口 → 额外口 → 文本框」的顺序合并，再一起送去清洁。

    因此 ``text`` 的默认值必须是空串 —— 否则连上 ``text_in`` 时会把示例文本一起粘进去。
    示例改用 ``placeholder`` 展示。

    额外口用 ``io.Autogrow``：``min=0`` 表示全部可选（不连也能跑），
    前端连上最后一个口时会自动再补一个，最多 :data:`EXTRA_TEXT_SLOT_NAMES` 个。
    """
    return [
        io.String.Input(
            "text_in",
            display_name="text in",
            optional=True,
            force_input=True,
            tooltip=(
                "Optional STRING socket. Whatever arrives here is cleaned first, then "
                "the extra text sockets (if any) and the content of the 'prompt text' "
                "box below are appended right after it and cleaned together. Leave it "
                "unconnected to clean the other sources alone."
            ),
        ),
        io.Autogrow.Input(
            "extra_texts",
            display_name="more text inputs",
            optional=True,
            template=io.Autogrow.TemplateNames(
                input=io.String.Input("text_in", display_name="text in"),
                names=list(EXTRA_TEXT_SLOT_NAMES),
                min=0,
            ),
            tooltip=_EXTRA_TEXTS_TOOLTIP,
        ),
        io.String.Input(
            "text",
            display_name="prompt text",
            multiline=True,
            dynamic_prompts=False,
            default="",
            placeholder=_EXAMPLE_TEXT,
            tooltip=(
                "Paste raw tags here: comma separated, one tag per line, or a mix of "
                "both. When 'text in' is connected, this box is appended after it (and "
                "after any extra text sockets), so you can mix an upstream prompt with "
                "extra tags typed here. Leave it empty to use only the sockets."
            ),
        ),
    ]


def _build_clean_inputs() -> list:
    """构造两个节点共享的清洁参数控件（每次返回全新实例，避免被 Schema 复用污染）。

    说明：Boolean 输入**故意不设置** ``label_on`` / ``label_off``。
    官方 i18n 的 ``nodeDefs.json`` 只覆盖 ``inputs.<id>.name`` 与 ``tooltip``，
    不覆盖 ``label_on``/``label_off``；只要留空，控件标签就会回退到 ``display_name``
    （英文）或翻译后的 ``name``（中文），从而做到真正的可翻译。
    """
    return [
        io.Combo.Input(
            "bracket_policy",
            display_name="bracket policy",
            options=BracketPolicy,
            default=DEFAULT_BRACKET_POLICY,
            tooltip=_BRACKET_TOOLTIP,
        ),
        io.Boolean.Input(
            "keep_weights",
            display_name="keep weights",
            default=True,
            tooltip=_KEEP_WEIGHTS_TOOLTIP,
        ),
        io.Boolean.Input(
            "underscore_to_space",
            display_name="underscore to space",
            default=True,
            tooltip=(
                "Convert underscores to spaces: drawing_bow -> drawing bow; "
                "sunna_(zenless_zone_zero) -> sunna (zenless zone zero)."
            ),
        ),
        io.Boolean.Input(
            "dedupe",
            display_name="dedupe",
            default=True,
            tooltip=(
                "Drop repeated tags (case-insensitive, leading and trailing "
                "whitespace ignored), keeping the first occurrence."
            ),
        ),
        io.Boolean.Input(
            "strip_blacklist",
            display_name="blacklist filter",
            default=True,
            tooltip=(
                "Drop dirty tags such as tagme / watermark / signature using the "
                "blacklist below."
            ),
        ),
        io.Boolean.Input(
            "lowercase",
            display_name="lowercase",
            default=False,
            tooltip=(
                "Lowercase every tag, matching the Anima community convention of "
                "lowercase multi-word tags."
            ),
        ),
        io.Combo.Input(
            "separator",
            display_name="separator",
            options=list(SEPARATOR_CHOICES),
            default=DEFAULT_SEPARATOR_CHOICE,
            tooltip=(
                "String used to join the tags. '逗号 + 空格' = comma followed by a "
                "space (default, recommended); '仅逗号' = bare comma."
            ),
        ),
        io.Boolean.Input(
            "normalize_fullwidth",
            display_name="fullwidth to halfwidth",
            default=True,
            advanced=True,
            tooltip=(
                "Convert full-width punctuation and full-width spaces to their "
                "half-width equivalents, e.g. （） -> () and ＿ -> _."
            ),
        ),
        io.String.Input(
            "blacklist",
            display_name="blacklist",
            multiline=True,
            default=DEFAULT_BLACKLIST,
            advanced=True,
            tooltip=_BLACKLIST_TOOLTIP,
        ),
    ]


def _make_options(
    *,
    bracket_policy,
    keep_weights,
    underscore_to_space,
    dedupe,
    lowercase,
    strip_blacklist,
    normalize_fullwidth,
    separator,
    blacklist,
) -> CleanOptions:
    """把节点控件值装配成引擎参数。

    每个参数都允许为 ``None``，表示「这个输入本次没被传进来」
    （例如旧工作流里还没有这个输入）。此时**回落到引擎默认值**，
    而不是 ``bool(None) == False`` —— 否则去重、黑名单这些开关会被静默关掉。
    """
    defaults = CleanOptions()

    def flag(value, fallback: bool) -> bool:
        return fallback if value is None else bool(value)

    return CleanOptions(
        underscore_to_space=flag(underscore_to_space, defaults.underscore_to_space),
        bracket_policy=BracketPolicy.coerce(bracket_policy),  # None 会回落到默认策略
        keep_weights=flag(keep_weights, defaults.keep_weights),
        dedupe=flag(dedupe, defaults.dedupe),
        lowercase=flag(lowercase, defaults.lowercase),
        strip_blacklist=flag(strip_blacklist, defaults.strip_blacklist),
        normalize_fullwidth=flag(normalize_fullwidth, defaults.normalize_fullwidth),
        # 下拉框给的是展示项，这里映射成真正的分隔符；兼容旧工作流里直接存 ", " / "," 的情况
        separator=SEPARATOR_VALUES.get(separator, separator or defaults.separator),
        blacklist=defaults.blacklist if blacklist is None else blacklist,
    )


def _resolve_source(text_in, text, extra_texts=None) -> str:
    """决定要清洁的原文。

    连上的口与文本框**都**算数，按固定顺序合并：
    ``text_in`` → ``extra_texts``（按 :data:`EXTRA_TEXT_SLOT_NAMES` 的声明顺序）
    → ``text`` 文本框。用换行符连接，因为清洗引擎本来就把换行当作标签分隔符。

    额外口由 ``io.Autogrow`` 组装成 ``{"text_in_2": "...", ...}`` 形式的字典；
    这里对非字典、非字符串的值一律忽略，保证旧工作流 / 手工构造的调用也不会崩。
    """
    parts: list[str] = []

    def add(value) -> None:
        if isinstance(value, str) and value:
            parts.append(value)

    add(text_in)
    if isinstance(extra_texts, dict):
        for name in EXTRA_TEXT_SLOT_NAMES:
            add(extra_texts.get(name))
    add(text)

    return "\n".join(parts)


def _publish_preview(text: str, node_cls) -> None:
    """把清洗结果推到节点画布上的文本区域显示（与核心 GetMeshInfo 的做法一致）。

    在 ComfyUI 之外调用（单元测试、脚本）时静默跳过，不抛异常、不影响执行。
    """
    try:
        from server import PromptServer
    except Exception:  # pragma: no cover - 非 ComfyUI 运行环境
        return

    server = getattr(PromptServer, "instance", None)
    unique_id = getattr(getattr(node_cls, "hidden", None), "unique_id", None)
    if server is None or not unique_id:
        return

    try:
        server.send_progress_text(text, unique_id)
    except Exception as exc:  # pragma: no cover - 推送失败不应影响出图
        LOGGER.debug("[PromptCleaner] 推送节点预览文本失败: %s", exc)


class PromptCleanerText(io.ComfyNode):
    """文本进、文本出的提示词清洁节点。"""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromoteCleaner_Text",
            display_name="Prompt Cleaner",
            category=CATEGORY,
            essentials_category=ESSENTIALS_CATEGORY,
            description=(
                "Cleans Danbooru-style underscore tags into prompt text that "
                "Anima Base can consume directly: comma+space separated, brackets "
                "escaped, deduplicated, residual separators removed, blacklist "
                "filtered. Weights such as (tag:1.2) are preserved. Several text "
                "inputs can be merged: every connected socket plus the text box is "
                "concatenated in order and cleaned as one prompt."
            ),
            search_aliases=[
                "prompt cleaner",
                "tag cleaner",
                "prompt formatter",
                "prompt sanitizer",
                "prompt merge",
                "concat prompts",
                "anima",
                "danbooru tags",
            ],
            is_output_node=True,
            hidden=[io.Hidden.unique_id],
            inputs=[
                *_build_text_inputs(),
                *_build_clean_inputs(),
            ],
            outputs=[
                io.String.Output(
                    "cleaned_text",
                    tooltip="Cleaned single-line prompt, ready for a CLIP Text Encode node.",
                ),
            ],
        )

    @classmethod
    def execute(
        cls,
        text_in=None,  # socket 输入：未连接时不会出现在 inputs 里，必须给默认值
        extra_texts=None,  # Autogrow 输入：全部未连接时是 {}，完全没传时是 None
        text=None,
        bracket_policy=None,
        keep_weights=None,
        underscore_to_space=None,
        dedupe=None,
        lowercase=None,
        strip_blacklist=None,
        separator=None,
        normalize_fullwidth=None,
        blacklist=None,
    ) -> io.NodeOutput:
        cleaned = clean_prompt(
            _resolve_source(text_in, text, extra_texts),
            _make_options(
                bracket_policy=bracket_policy,
                keep_weights=keep_weights,
                underscore_to_space=underscore_to_space,
                dedupe=dedupe,
                lowercase=lowercase,
                strip_blacklist=strip_blacklist,
                normalize_fullwidth=normalize_fullwidth,
                separator=separator,
                blacklist=blacklist,
            ),
        )
        _publish_preview(cleaned, cls)
        return io.NodeOutput(cleaned, ui=ui.PreviewText(cleaned))


class PromptCleanerClipEncode(io.ComfyNode):
    """CLIP + 文本进，同时输出 CONDITIONING 与清洗后的文本。"""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PromoteCleaner_ClipEncode",
            display_name="Prompt Cleaner (CLIP Text Encode)",
            category=CATEGORY,
            essentials_category=ESSENTIALS_CATEGORY,
            description=(
                "Cleans the prompt with Prompt Cleaner rules and then encodes it "
                "with CLIP. One output goes straight to the sampler as "
                "CONDITIONING, the other exposes the cleaned text for reuse or "
                "inspection."
            ),
            search_aliases=[
                "prompt cleaner clip",
                "clean clip text encode",
                "prompt encode cleaner",
                "anima encode",
            ],
            hidden=[io.Hidden.unique_id],
            inputs=[
                io.Clip.Input(
                    "clip",
                    display_name="clip",
                    tooltip=(
                        "CLIP / text encoder used to encode the prompt "
                        "(Anima uses qwen_3_06b_base)."
                    ),
                ),
                *_build_text_inputs(),
                *_build_clean_inputs(),
            ],
            outputs=[
                io.Conditioning.Output(
                    "conditioning",
                    tooltip=(
                        "Encoded conditioning of the cleaned prompt, ready for a sampler."
                    ),
                ),
                io.String.Output(
                    "cleaned_text",
                    tooltip=(
                        "Cleaned single-line prompt, for reuse or for double-checking."
                    ),
                ),
            ],
        )

    @classmethod
    def execute(
        cls,
        clip=None,  # socket 输入：未连接时不会出现在 inputs 里，必须给默认值
        text_in=None,
        extra_texts=None,
        text=None,
        bracket_policy=None,
        keep_weights=None,
        underscore_to_space=None,
        dedupe=None,
        lowercase=None,
        strip_blacklist=None,
        separator=None,
        normalize_fullwidth=None,
        blacklist=None,
    ) -> io.NodeOutput:
        if clip is None:
            raise RuntimeError(
                "ERROR: clip input is invalid: None\n\n"
                "If the clip is from a checkpoint loader node your checkpoint does not "
                "contain a valid clip or text encoder model."
            )

        cleaned = clean_prompt(
            _resolve_source(text_in, text, extra_texts),
            _make_options(
                bracket_policy=bracket_policy,
                keep_weights=keep_weights,
                underscore_to_space=underscore_to_space,
                dedupe=dedupe,
                lowercase=lowercase,
                strip_blacklist=strip_blacklist,
                normalize_fullwidth=normalize_fullwidth,
                separator=separator,
                blacklist=blacklist,
            ),
        )
        _publish_preview(cleaned, cls)
        tokens = clip.tokenize(cleaned)
        return io.NodeOutput(
            clip.encode_from_tokens_scheduled(tokens),
            cleaned,
            ui=ui.PreviewText(cleaned),
        )
