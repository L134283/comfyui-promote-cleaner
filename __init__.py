"""Comfyui-Promote-Cleaner

把 Danbooru 风格的「老式下划线标签」清洗成 Anima Base 可直接食用的标准提示词格式。

节点入口使用 ComfyUI V3 扩展 API（``comfy_entrypoint``）。
注意：这里 **不能** 定义 ``NODE_CLASS_MAPPINGS``，
否则 ComfyUI 的加载器（``nodes.py`` 中的 ``load_custom_node``）会优先走 V1 分支，
导致 ``comfy_entrypoint`` 被跳过、节点无法注册。
"""

from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .nodes import PromptCleanerClipEncode, PromptCleanerText

#: 前端扩展目录：ComfyUI 会加载其中的 ``*.js``（大按钮 + 设置弹窗 + 文本输入口增减）。
#: ``nodes.py`` 的 ``load_custom_node`` 只认模块顶层的这个变量，所以必须写在这里。
WEB_DIRECTORY = "./web"

__all__ = [
    "PromptCleanerExtension",
    "comfy_entrypoint",
    "PromptCleanerText",
    "PromptCleanerClipEncode",
    "WEB_DIRECTORY",
]


class PromptCleanerExtension(ComfyExtension):
    """注册本插件提供的全部节点。"""

    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            PromptCleanerText,
            PromptCleanerClipEncode,
        ]


async def comfy_entrypoint() -> PromptCleanerExtension:
    """ComfyUI 加载自定义节点时调用的入口。"""
    print("[PromptCleaner] loaded")
    return PromptCleanerExtension()
