"""节点契约测试：``io.Schema`` 的输入 与 ``execute`` 的签名必须始终一致。

这个文件是**回归测试**，起因是一个真实事故：

    用户在一个「保存于 text_in 存在之前」的工作流里跑节点，
    ComfyUI 报 TypeError: PromptCleanerText.execute() missing 1 required
    positional argument: 'text_in'

根因（``ComfyUI/execution.py`` 第 168 行 ``for x in inputs:``）：
``input_data_all`` **只包含工作流里实际存在的输入键**，不会补默认值。
widget 输入前端总会序列化，所以从不缺失；而 **socket 输入未连接时根本不会出现在
``inputs`` 里** —— 因此 socket 输入在 ``execute`` 签名里必须带默认值。

本文件需要 ComfyUI 环境（要 import ``comfy_api.latest``）；
在纯 Python 环境下会自动跳过，不报错。

跑法：
    python tests/test_node_contract.py
    pytest tests/test_node_contract.py
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMFY_ROOT = os.path.dirname(os.path.dirname(_PLUGIN_DIR))

if _COMFY_ROOT not in sys.path:
    sys.path.insert(0, _COMFY_ROOT)

try:
    from comfy_api.latest import io  # noqa: F401
except Exception:  # pragma: no cover - 非 ComfyUI 环境
    io = None


def _load_nodes_module():
    """按 ComfyUI 加载器的方式加载本插件包。"""
    sys_module_name = _PLUGIN_DIR.replace(".", "_x_")
    if sys_module_name in sys.modules:
        return sys.modules[sys_module_name]
    spec = importlib.util.spec_from_file_location(
        sys_module_name,
        os.path.join(_PLUGIN_DIR, "__init__.py"),
        submodule_search_locations=[_PLUGIN_DIR],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[sys_module_name] = module
    spec.loader.exec_module(module)
    return module


def _require_comfyui():
    if io is None:
        print("[skip] 当前环境没有 comfy_api，跳过节点契约测试（需要 ComfyUI）")
        return None
    return _load_nodes_module()


def _node_classes():
    module = _require_comfyui()
    if module is None:
        return None

    import asyncio

    async def _load():
        extension = await module.comfy_entrypoint()
        return await extension.get_node_list()

    return asyncio.run(_load())


def test_每个节点都注册了_node_id_与分类():
    nodes = _node_classes()
    if nodes is None:
        return
    assert nodes, "至少要注册一个节点"
    for cls in nodes:
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id, cls
        assert schema.display_name, cls
        assert schema.category, cls


def test_schema_输入与_execute_参数一一对应():
    nodes = _node_classes()
    if nodes is None:
        return
    for cls in nodes:
        schema = cls.GET_SCHEMA()
        params = set(inspect.signature(cls.execute).parameters) - {"cls"}
        input_ids = {item.id for item in schema.inputs}
        assert params == input_ids, (
            f"{schema.node_id}: schema 输入与 execute 参数不一致，"
            f"差集 = {params ^ input_ids}（漏写参数会在执行时报 TypeError）"
        )


def test_所有_socket_输入都必须有默认值():
    """widget 输入前端总会传；socket 输入未连接时不会传，必须靠签名默认值兜底。"""
    nodes = _node_classes()
    if nodes is None:
        return
    for cls in nodes:
        schema = cls.GET_SCHEMA()
        params = inspect.signature(cls.execute).parameters
        for item in schema.inputs:
            is_widget = hasattr(item, "default") and not getattr(item, "force_input", None)
            if is_widget:
                continue
            assert params[item.id].default is not inspect.Parameter.empty, (
                f"{schema.node_id}.{item.id} 是 socket 输入（无控件），"
                "execute 参数必须带默认值，否则旧工作流会 TypeError"
            )


def test_不传任何输入也能执行():
    """最极端的兼容性检查：`.execute()` 空参调用不应崩溃。"""
    nodes = _node_classes()
    if nodes is None:
        return
    import asyncio

    text_node = next(c for c in nodes if c.GET_SCHEMA().node_id == "PromoteCleaner_Text")
    out = text_node.execute()
    assert out.result == ("",), out.result


def test_缺输入的_None_不会静默关掉开关():
    """``bool(None) == False`` 的陷阱：缺输入时必须回落到引擎默认值。"""
    nodes = _node_classes()
    if nodes is None:
        return

    text_node = next(c for c in nodes if c.GET_SCHEMA().node_id == "PromoteCleaner_Text")

    # 只传 text，去重 / 黑名单 / 括号转义都应保持默认开启
    only_text = text_node.execute(text="drawing_bow, drawing_bow")
    assert only_text.result == ("drawing bow",), only_text.result

    filtered = text_node.execute(text="tagme, 1girl")
    assert filtered.result == ("1girl",), filtered.result


def test_额外文本插槽会展开成可选输入():
    """Autogrow 输入必须把每个额外口都展开成**可选**输入，否则不连就报错。

    展开规则由 ComfyUI 的 ``get_finalized_class_inputs`` 负责，这里直接调它，
    确保「前端按 ``extra_texts.text_in_N`` 命名插槽」这套约定真的成立。
    """
    nodes = _node_classes()
    if nodes is None:
        return

    from comfy_api.latest import _io

    for cls in nodes:
        schema = cls.GET_SCHEMA()
        autogrow = next((i for i in schema.inputs if i.id == "extra_texts"), None)
        assert autogrow is not None, f"{schema.node_id} 缺少额外文本插槽"

        names = autogrow.template.names
        assert names and names[0] == "text_in_2", names

        # 什么都不连：不能出现 required，且必须能回落到空字典
        inputs, _, v3_data = _io.get_finalized_class_inputs(cls.INPUT_TYPES(), {})
        assert all(
            f"extra_texts.{name}" not in inputs.get("required", {}) for name in names
        ), f"{schema.node_id}: 额外文本插槽不应该出现在 required 里"
        merged = _io.build_nested_inputs({}, v3_data)
        assert merged["extra_texts"] == {}, merged

        # 连上第 2、第 4 个口：两者都必须被识别并归到 extra_texts 字典里
        live = {"extra_texts.text_in_2": "a", "extra_texts.text_in_4": "b"}
        _, _, v3_data = _io.get_finalized_class_inputs(cls.INPUT_TYPES(), live)
        merged = _io.build_nested_inputs(dict(live), v3_data)
        assert merged["extra_texts"] == {"text_in_2": "a", "text_in_4": "b"}, merged


def test_多来源文本按_首口_额外口_文本框_的顺序合并():
    nodes = _node_classes()
    if nodes is None:
        return

    text_node = next(c for c in nodes if c.GET_SCHEMA().node_id == "PromoteCleaner_Text")

    out = text_node.execute(
        text_in="1girl",
        # 故意乱序传，且跳过中间的口：输出必须按声明的槽位顺序排列
        extra_texts={"text_in_3": "smile", "text_in_2": "solo"},
        text="best_quality",
    )
    assert out.result == ("1girl, solo, smile, best quality",), out.result

    # 额外口与文本框里的重复标签也会被一起去重（合并后统一清洁）
    deduped = text_node.execute(extra_texts={"text_in_2": "1girl"}, text="1girl")
    assert deduped.result == ("1girl",), deduped.result


def test_额外文本插槽的脏值不会让节点崩溃():
    """旧工作流 / 手工调用可能塞进非字典、非字符串的值，必须安全忽略。"""
    nodes = _node_classes()
    if nodes is None:
        return

    text_node = next(c for c in nodes if c.GET_SCHEMA().node_id == "PromoteCleaner_Text")

    assert text_node.execute(extra_texts=_StubValue(), text="1girl").result == ("1girl",)
    # 只有 text_in_4 是有效字符串，其余（None / 占位对象）被忽略；额外口排在文本框之前
    assert text_node.execute(
        extra_texts={"text_in_2": None, "text_in_3": _StubValue(), "text_in_4": "smile"},
        text="1girl",
    ).result == ("smile, 1girl",)


def test_旧工作流缺少_socket_输入仍可运行():
    """精确复现事故场景：工作流里只有 widget 输入（没有 text_in）。"""
    nodes = _node_classes()
    if nodes is None:
        return

    for cls in nodes:
        schema = cls.GET_SCHEMA()
        legacy = {
            item.id: item.default
            for item in schema.inputs
            if hasattr(item, "default") and not getattr(item, "force_input", None)
        }
        for item in schema.inputs:
            if not hasattr(item, "default"):
                legacy[item.id] = _StubValue()

        if schema.node_id == "PromoteCleaner_Text":
            legacy["text"] = "drawing_bow, sunna_(zenless_zone_zero)"
            out = cls.execute(**legacy)
            assert out.result == ("drawing bow, sunna \\(zenless zone zero\\)",), out.result
        else:
            out = cls.execute(**legacy)
            assert out.result[1] == "" or isinstance(out.result[1], str), out.result


class _StubValue:
    """给 socket 输入用的占位对象（这里只需要不是 None）。"""

    def tokenize(self, text):
        return text

    def encode_from_tokens_scheduled(self, tokens):
        return tokens


def test_两个节点都在中文语言包里有翻译():
    nodes = _node_classes()
    if nodes is None:
        return

    import json

    locale_path = os.path.join(_PLUGIN_DIR, "locales", "zh", "nodeDefs.json")
    with open(locale_path, encoding="utf-8") as fp:
        locale = json.load(fp)

    for cls in nodes:
        schema = cls.GET_SCHEMA()
        entry = locale.get(schema.node_id)
        assert entry, f"{schema.node_id} 缺少中文翻译"
        assert entry.get("display_name"), schema.node_id
        for item in schema.inputs:
            assert item.id in entry.get("inputs", {}), f"{schema.node_id}.{item.id} 缺少中文翻译"


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
