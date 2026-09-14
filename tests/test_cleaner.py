"""Prompt Cleaner 清洗引擎单元测试。

两种跑法都可以：

* ``pytest tests/test_cleaner.py``
* ``python tests/test_cleaner.py``

本测试**不依赖 ComfyUI**，只测 ``prompt_cleaner`` 纯函数引擎。
"""

from __future__ import annotations

import os
import sys

# 让 `python tests/test_cleaner.py` 也能直接 import 到插件根目录下的 prompt_cleaner 包。
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from prompt_cleaner import (  # noqa: E402
    BracketPolicy,
    CleanOptions,
    clean_prompt,
    escape_brackets,
    normalize_escapes,
    weight_spans,
)


# --------------------------------------------------------------------------
# 用户给的 3 组基准用例
# --------------------------------------------------------------------------

def test_underscore_to_space():
    assert clean_prompt("drawing_bow") == "drawing bow"


def test_parens_escaped():
    assert clean_prompt("sunna (zenless zone zero)") == "sunna \\(zenless zone zero\\)"


def test_underscore_and_parens_combined():
    assert clean_prompt("sunna_(zenless_zone_zero)") == "sunna \\(zenless zone zero\\)"


def test_user_example_line():
    assert (
        clean_prompt("drawing_bow, sunna_(zenless_zone_zero)")
        == "drawing bow, sunna \\(zenless zone zero\\)"
    )


# --------------------------------------------------------------------------
# 分隔与残留清理
# --------------------------------------------------------------------------

def test_newline_split():
    assert (
        clean_prompt("drawing_bow\nsunna_(zenless_zone_zero)\n\nbest_quality")
        == "drawing bow, sunna \\(zenless zone zero\\), best quality"
    )


def test_mixed_separators_and_extra_commas():
    assert clean_prompt("a,,, b; c；d，e\n, f, ") == "a, b, c, d, e, f"


def test_empty_input():
    assert clean_prompt("") == ""
    assert clean_prompt("   ,, ;\n , ") == ""
    assert clean_prompt(",,,") == ""


def test_separator_option():
    assert clean_prompt("a, b", CleanOptions(separator=",")) == "a,b"


def test_custom_separator_fallback_when_blank():
    assert clean_prompt("a, b", CleanOptions(separator="")) == "a, b"


# --------------------------------------------------------------------------
# 去重
# --------------------------------------------------------------------------

def test_dedupe_ignores_case_and_padding():
    assert clean_prompt("Drawing Bow, drawing bow, DRAWING_BOW") == "Drawing Bow"


def test_dedupe_after_normalization():
    # 下划线形态与空格形态是同一个标签
    assert clean_prompt("drawing_bow, drawing bow") == "drawing bow"


def test_dedupe_disabled():
    assert clean_prompt("a, a", CleanOptions(dedupe=False)) == "a, a"


# --------------------------------------------------------------------------
# 全角 / 大小写
# --------------------------------------------------------------------------

def test_fullwidth_normalization():
    assert clean_prompt("（masterpiece）, 1girl，best_quality；safe") == (
        "\\(masterpiece\\), 1girl, best quality, safe"
    )


def test_fullwidth_disabled():
    # 关掉全角规整后，全角括号原样保留（半角括号转义规则不作用于全角字符）
    assert clean_prompt("（a）", CleanOptions(normalize_fullwidth=False)) == "（a）"


def test_lowercase_option():
    assert clean_prompt("Drawing Bow, BEST Quality", CleanOptions(lowercase=True)) == (
        "drawing bow, best quality"
    )


# --------------------------------------------------------------------------
# 下划线开关
# --------------------------------------------------------------------------

def test_underscore_kept_when_disabled():
    assert clean_prompt("drawing_bow", CleanOptions(underscore_to_space=False)) == "drawing_bow"


def test_underscore_inside_fullwidth_parens():
    assert clean_prompt("sunna＿(zenless＿zone＿zero)") == "sunna \\(zenless zone zero\\)"


# --------------------------------------------------------------------------
# 括号策略
# --------------------------------------------------------------------------

def test_bracket_policy_escape_all():
    assert (
        clean_prompt("{{safe}} [1girl]", CleanOptions(bracket_policy=BracketPolicy.ESCAPE_ALL))
        == "\\{\\{safe\\}\\} \\[1girl\\]"
    )


def test_bracket_policy_none():
    assert (
        clean_prompt("sunna (zenless zone zero)", CleanOptions(bracket_policy=BracketPolicy.NONE))
        == "sunna (zenless zone zero)"
    )


def test_bracket_policy_accepts_string_value():
    options = CleanOptions(bracket_policy=BracketPolicy.PARENS_ONLY.value)
    assert clean_prompt("a (b)", options) == "a \\(b\\)"


def test_bracket_policy_unknown_value_falls_back():
    assert clean_prompt("a (b)", CleanOptions(bracket_policy="不存在")) == "a \\(b\\)"


def test_unbalanced_brackets_do_not_crash():
    assert clean_prompt("a ( b ) c )") == "a \\( b \\) c \\)"
    assert clean_prompt("(((") == "\\(\\(\\("
    assert clean_prompt(")") == "\\)"


def test_unbalanced_brackets_do_not_hang():
    """回归用例：曾经因为「递归扫描未闭合括号时不推进下标」导致死循环。"""
    assert clean_prompt("(" * 200) == "\\(" * 200
    assert clean_prompt(")" * 200) == "\\)" * 200
    assert clean_prompt("((masterpiece:1.2)" * 20) is not None
    assert clean_prompt(")(" * 200) is not None


def test_deeply_nested_weight_is_preserved():
    nested = "(" * 8 + "a:1.2" + ")" * 8
    assert clean_prompt(nested) == nested


def test_deeply_nested_bare_parens_are_escaped():
    nested = "(" * 8 + "a" + ")" * 8
    assert clean_prompt(nested) == "\\(" * 8 + "a" + "\\)" * 8


def test_normalize_escapes_restores_literal_brackets():
    assert normalize_escapes("a \\(b\\) \\[c\\]") == "a (b) [c]"


def test_already_escaped_input_is_idempotent():
    once = clean_prompt("sunna_(zenless_zone_zero)")
    assert clean_prompt(once) == once


def test_escape_is_idempotent_for_escape_all():
    options = CleanOptions(bracket_policy=BracketPolicy.ESCAPE_ALL)
    once = clean_prompt("{{a}} [b] (c)", options)
    assert clean_prompt(once, options) == once


def test_escape_brackets_direct():
    assert escape_brackets("a(b)", BracketPolicy.PARENS_ONLY) == "a\\(b\\)"
    assert escape_brackets("a[b]", BracketPolicy.PARENS_ONLY) == "a[b]"
    assert escape_brackets("a[b]", BracketPolicy.ESCAPE_ALL) == "a\\[b\\]"
    assert escape_brackets("a[b]", BracketPolicy.NONE) == "a[b]"
    assert escape_brackets("(a:1.2)", BracketPolicy.PARENS_ONLY) == "(a:1.2)"
    assert (
        escape_brackets("(a:1.2)", BracketPolicy.PARENS_ONLY, keep_weights=False) == "\\(a:1.2\\)"
    )


# --------------------------------------------------------------------------
# 权重语法保留
# --------------------------------------------------------------------------

def test_explicit_weight_is_preserved():
    assert clean_prompt("(masterpiece:1.2)") == "(masterpiece:1.2)"


def test_weight_with_underscore_and_spaces():
    assert clean_prompt("(best_quality: 1.3)") == "(best quality: 1.3)"
    assert clean_prompt("(from_side:1.2)") == "(from side:1.2)"


def test_weight_mixed_with_literal_parens():
    assert clean_prompt("sunna (zenless zone zero) (masterpiece:1.2)") == (
        "sunna \\(zenless zone zero\\) (masterpiece:1.2)"
    )


def test_nested_weight_is_preserved():
    assert clean_prompt("((masterpiece:1.2))") == "((masterpiece:1.2))"


def test_bare_parens_are_still_escaped():
    assert clean_prompt("(masterpiece)") == "\\(masterpiece\\)"
    assert clean_prompt("((masterpiece))") == "\\(\\(masterpiece\\)\\)"


def test_empty_parens_are_escaped():
    assert clean_prompt("()") == "\\(\\)"


def test_weight_preserved_under_escape_all():
    options = CleanOptions(bracket_policy=BracketPolicy.ESCAPE_ALL)
    assert clean_prompt("(masterpiece:1.2)", options) == "(masterpiece:1.2)"


def test_weight_can_be_disabled():
    assert clean_prompt("(masterpiece:1.2)", CleanOptions(keep_weights=False)) == (
        "\\(masterpiece:1.2\\)"
    )


def test_weight_is_idempotent():
    once = clean_prompt("sunna_(zenless_zone_zero), (masterpiece:1.2)")
    assert once == "sunna \\(zenless zone zero\\), (masterpiece:1.2)"
    assert clean_prompt(once) == once


def test_weight_spans_detection():
    assert weight_spans("(a:1.2)") == [(0, 7)]
    assert weight_spans("x (a:1.2) y") == [(2, 9)]
    assert weight_spans("(a)") == []
    assert weight_spans("()") == []
    assert weight_spans("a (b) (c:1.1)") == [(6, 13)]


# --------------------------------------------------------------------------
# 黑名单
# --------------------------------------------------------------------------

def test_default_blacklist_filters_meta_tags():
    assert clean_prompt("1girl, tagme, watermark, year 2024, best quality") == (
        "1girl, best quality"
    )


def test_default_blacklist_is_exact_match_not_contains():
    # signature 不该把 signature move 一起干掉
    assert clean_prompt("signature move, signature") == "signature move"


def test_blacklist_matches_underscore_form():
    assert clean_prompt("twitter_username, 1girl") == "1girl"
    assert (
        clean_prompt("twitter_username, 1girl", CleanOptions(underscore_to_space=False)) == "1girl"
    )


def test_blacklist_can_be_disabled():
    assert clean_prompt("tagme, 1girl", CleanOptions(strip_blacklist=False)) == "tagme, 1girl"


def test_custom_blacklist_only():
    assert clean_prompt("foo, bar", CleanOptions(blacklist="foo")) == "bar"


def test_empty_blacklist_disables_filtering():
    assert clean_prompt("tagme", CleanOptions(blacklist="")) == "tagme"


def test_blacklist_regex_rule_and_bad_regex():
    options = CleanOptions(blacklist="re:^year\\s+\\d{4}$\nre:[不合法")
    assert clean_prompt("1girl, year 2024, year 2024 remake", options) == "1girl, year 2024 remake"


def test_blacklist_supports_comments_and_blank_lines():
    options = CleanOptions(blacklist="# 注释\n\nfoo\n")
    assert clean_prompt("foo, bar", options) == "bar"


# --------------------------------------------------------------------------
# 真实场景回归
# --------------------------------------------------------------------------

def test_natural_language_sentence_kept_whole():
    assert clean_prompt("a girl sitting on a bench") == "a girl sitting on a bench"


def test_realistic_prompt():
    raw = (
        "masterpiece, best_quality, 1girl, solo,\n"
        "sunna_(zenless_zone_zero), drawing_bow, (from_side), tagme,\n"
        "watermark, drawing_bow, year 2023, 1girl"
    )
    assert clean_prompt(raw) == (
        "masterpiece, best quality, 1girl, solo, "
        "sunna \\(zenless zone zero\\), drawing bow, \\(from side\\)"
    )


def test_realistic_prompt_with_weights():
    raw = (
        "masterpiece, (best_quality:1.3), 1girl, sunna_(zenless_zone_zero),\n"
        "((very_aesthetic:1.15)), drawing_bow, tagme, (from_side)"
    )
    assert clean_prompt(raw) == (
        "masterpiece, (best quality:1.3), 1girl, "
        "sunna \\(zenless zone zero\\), ((very aesthetic:1.15)), "
        "drawing bow, \\(from side\\)"
    )


if __name__ == "__main__":
    import traceback

    failures: list[str] = []
    for test_name, test_func in sorted(list(globals().items())):
        if not test_name.startswith("test_") or not callable(test_func):
            continue
        try:
            test_func()
        except Exception:
            failures.append(test_name)
            print(f"[FAIL] {test_name}")
            traceback.print_exc()
        else:
            print(f"[ OK ] {test_name}")

    total = len([n for n in globals() if n.startswith("test_")])
    print(f"\n{total - len(failures)}/{total} passed")
    sys.exit(1 if failures else 0)
