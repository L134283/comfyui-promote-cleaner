"""前端 / 后端契约测试：**不需要 ComfyUI**，只要 Python 标准库。

起因：``web/js/prompt_cleaner.js`` 里硬编码了三份「必须与后端对齐的清单」——

1. 负责哪些节点（``NODE_TYPES`` ↔ ``nodes.py`` 的 ``node_id``）
2. 哪些控件要收进设置弹窗（``OPTION_WIDGETS`` ↔ schema 里的输入 id）
3. 额外文本插槽叫什么（``FALLBACK_SLOT_NAMES`` / ``SLOT_PREFIX`` ↔ `Autogrow` 的声明）

这些名字写错**不会报任何错**，只会静默失效：控件不收起来、弹窗改了不生效、
或者前端加出来的口后端根本不认。而 ``tests/test_node_contract.py`` 需要 ComfyUI 环境，
CI 里跑不了，所以这里用纯文本解析把「跨文件一致性」钉住 —— 任何一边改名都会立刻红。

另外还检查**帮助页的位置**：ComfyUI 前端实际请求的是
``/extensions/<包名>/docs/<node_id>.md``，也就是帮助页必须在 ``WEB_DIRECTORY``（``web/``）里面，
放在包根的 ``docs/`` 是取不到的（v1.1.0 就踩过这个坑）。

跑法：
    python tests/test_frontend_contract.py
    pytest tests/test_frontend_contract.py
"""

from __future__ import annotations

import os
import re
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JS_PATH = os.path.join(_PLUGIN_DIR, "web", "js", "prompt_cleaner.js")
_NODES_PATH = os.path.join(_PLUGIN_DIR, "nodes.py")
_NODE_DOCS_DIR = os.path.join(_PLUGIN_DIR, "web", "docs")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fp:
        return fp.read()


def _js_array(source: str, name: str) -> list[str]:
    """从 JS 源码里取出 ``const <name> = [ ... ]`` 或 ``= new Set([ ... ])`` 的字符串字面量。"""
    match = re.search(rf"const\s+{name}\s*=\s*(?:new\s+Set\()?\s*\[(.*?)\]", source, re.S)
    assert match, f"在 prompt_cleaner.js 里找不到 {name} 数组"
    return re.findall(r'"([^"]+)"', match.group(1))


def _js_string(source: str, name: str) -> str:
    match = re.search(rf"const\s+{name}\s*=\s*\"([^\"]+)\"", source)
    assert match, f"在 prompt_cleaner.js 里找不到 {name}"
    return match.group(1)


def _node_ids(nodes_source: str) -> set[str]:
    return set(re.findall(r'node_id\s*=\s*"([^"]+)"', nodes_source))


def _schema_input_ids(nodes_source: str) -> set[str]:
    return set(re.findall(r'io\.\w+\.Input\(\s*"([^"]+)"', nodes_source))


def _extra_slot_names(nodes_source: str) -> list[str]:
    """还原 ``EXTRA_TEXT_SLOT_NAMES = tuple(f"text_in_{i}" for i in range(a, b))``。"""
    match = re.search(
        r'EXTRA_TEXT_SLOT_NAMES.{0,120}?range\((\d+)\s*,\s*(\d+)\)', nodes_source, re.S
    )
    assert match, "nodes.py 里的 EXTRA_TEXT_SLOT_NAMES 不再是 range(a, b) 形式，请同步本测试"
    start, stop = int(match.group(1)), int(match.group(2))
    prefix = re.search(r'EXTRA_TEXT_SLOT_NAMES.{0,120}?f"([^"{]+)\{', nodes_source, re.S)
    assert prefix, "nodes.py 里的 EXTRA_TEXT_SLOT_NAMES 前缀解析失败"
    return [f"{prefix.group(1)}{index}" for index in range(start, stop)]


def test_js_负责的节点与_nodes_py_一致():
    js_source = _read(_JS_PATH)
    node_ids = _node_ids(_read(_NODES_PATH))
    assert set(_js_array(js_source, "NODE_TYPES")) == node_ids, (
        f"前端 NODE_TYPES 与后端 node_id 不一致：{node_ids}"
    )


def test_设置弹窗里的控件名都真实存在():
    """OPTION_WIDGETS 里写错名字 => 控件不会被收起来，弹窗也改不到它。"""
    js_source = _read(_JS_PATH)
    hidden = _js_array(js_source, "OPTION_WIDGETS")
    assert hidden, "OPTION_WIDGETS 为空"
    unknown = [name for name in hidden if name not in _schema_input_ids(_read(_NODES_PATH))]
    assert not unknown, f"这些控件名在后端 schema 里不存在：{unknown}"


def test_开关与下拉清单都在_OPTION_WIDGETS_里():
    """弹窗要能编辑的控件，必须同时也被 hideWidgetForGood 收走，否则会出现两套 UI。"""
    js_source = _read(_JS_PATH)
    hidden = set(_js_array(js_source, "OPTION_WIDGETS"))
    for array_name in ("BOOLEAN_OPTIONS", "COMBO_OPTIONS"):
        block = re.search(
            rf"const\s+{array_name}\s*=\s*\[(.*?)\n\];", js_source, re.S
        )
        assert block, f"找不到 {array_name}"
        ids = re.findall(r'id:\s*"([^"]+)"', block.group(1))
        assert ids, f"{array_name} 里没解析到 id"
        missing = [name for name in ids if name not in hidden]
        assert not missing, f"{array_name} 里的 {missing} 没被收进设置弹窗"


def test_额外文本插槽名与后端_Autogrow_声明一致():
    """前端手加/手删插槽时用的名字，必须与后端 Autogrow 展开出来的名字完全相同。"""
    js_source = _read(_JS_PATH)
    nodes_source = _read(_NODES_PATH)

    assert _js_array(js_source, "FALLBACK_SLOT_NAMES") == _extra_slot_names(nodes_source), (
        "前端 FALLBACK_SLOT_NAMES 与后端 EXTRA_TEXT_SLOT_NAMES 不一致"
    )

    autogrow_id = re.search(r'io\.Autogrow\.Input\(\s*"([^"]+)"', nodes_source)
    assert autogrow_id, "nodes.py 里找不到 Autogrow 输入"
    assert _js_string(js_source, "SLOT_PREFIX") == f"{autogrow_id.group(1)}.", (
        "前端 SLOT_PREFIX 必须等于「Autogrow 输入名 + .」"
    )


def test_节点帮助页放在_WEB_DIRECTORY_里():
    """前端请求 /extensions/<包名>/docs/<node_id>.md，所以帮助页必须位于 web/docs/。"""
    node_ids = sorted(_node_ids(_read(_NODES_PATH)))
    assert node_ids, "nodes.py 里没解析到 node_id"
    for node_id in node_ids:
        path = os.path.join(_NODE_DOCS_DIR, f"{node_id}.md")
        assert os.path.isfile(path), (
            f"缺少帮助页 {os.path.relpath(path, _PLUGIN_DIR)}："
            "放在包根的 docs/ 前端取不到，必须在 WEB_DIRECTORY 里面"
        )

    stray = os.path.join(_PLUGIN_DIR, "docs")
    assert not os.path.exists(stray), "包根不应该再有 docs/ 目录，帮助页请放 web/docs/"


if __name__ == "__main__":
    import traceback

    # 先把用例列表固定下来：循环变量 `test_name` / `test_func` 之后也会成为全局变量，
    # 如果直接数 globals()，它们会被当成用例（旧写法会多报 2 例）。
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]

    failures: list[str] = []
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception:
            failures.append(test_name)
            print(f"[FAIL] {test_name}")
            traceback.print_exc()
        else:
            print(f"[ OK ] {test_name}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
