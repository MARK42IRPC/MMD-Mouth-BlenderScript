"""Blender interface translations for the add-on."""

from __future__ import annotations

import bpy


_DOMAIN = __package__ or "mmd_mouth"

_ZH_HANS = {
    "MMD Models": "MMD 模型",
    "Mouth Clips": "口型片段",
    "Unnamed Model": "未命名模型",
    "Unnamed Clip": "未命名片段",
    "Name": "名称",
    "Root": "根对象",
    "Mouth Morphs:": "口型形态键：",
    "Scan": "扫描",
    "Audio": "音频",
    "Preview Volume": "预览响度",
    "Start Frame": "起始帧",
    "Language": "语言",
    "Audio Offset (s)": "音频偏移（秒）",
    "Duration (s)": "时长（秒）",
    "Render FPS:": "渲染帧率：",
    "Generation Mode": "生成模式",
    "Mouth Blend": "口型混合",
    "Envelope easing and adjacent-vowel blending mode": "包络缓动与相邻元音混合模式",
    "Linear": "线性",
    "Smoothstep": "平滑步进",
    "Sine": "正弦",
    "Ease In": "缓入",
    "Ease Out": "缓出",
    "Keep direct linear attack/release without vowel crossfade": (
        "保持线性起落，不进行元音交叉混合"
    ),
    "Cubic smooth transition with adjacent-vowel crossfade": (
        "使用三次平滑过渡，并在相邻元音之间交叉混合"
    ),
    "Cosine smooth transition with adjacent-vowel crossfade": (
        "使用正弦平滑过渡，并在相邻元音之间交叉混合"
    ),
    "Slow entry and faster exit with adjacent-vowel crossfade": (
        "缓慢进入、快速退出，并在相邻元音之间交叉混合"
    ),
    "Faster entry and slower exit with adjacent-vowel crossfade": (
        "快速进入、缓慢退出，并在相邻元音之间交叉混合"
    ),
    "Mouth Strength": "口型强度",
    "Generate Mouth": "生成口型",
    "Regenerate Mouth": "重新生成口型",
    "Regenerate": "重新生成",
    "Recognize Audio": "识别音频",
    "Recognize Only": "仅识别",
    "Clear Generated Animation": "清除已生成动画",
    "Clear Animation": "清除动画",
    "Delete Clip": "删除片段",
    "Status:": "状态：",
    "Transcript": "识别文本",
    "Runtime": "运行环境",
    "Recognition Models": "识别模型",
    "Add Custom": "添加自定义模型",
    "Worker Mode": "Worker 模式",
    "Worker Executable": "Worker 可执行文件",
    "Worker Python": "Worker Python",
    "Cache Directory": "缓存目录",
    "Display Name": "显示名称",
    "Model ID": "模型 ID",
    "Model Directory": "模型目录",
    "Priority": "优先级",
    "Calibration Bias": "校准偏置",
    "Calibration Temperature": "校准温度",
    "Add Model": "添加模型",
    "Remove Model": "删除模型",
    "Add Clip": "添加片段",
    "Add Vosk Model": "添加 Vosk 模型",
    "Remove Vosk Model": "删除 Vosk 模型",
    "Check Runtime": "检查运行环境",
    "Scan Mouth Morphs": "扫描口型形态键",
    "Cancel": "取消",
    "Bake": "烘焙",
    "Driver": "驱动器",
    "Chinese": "中文",
    "Japanese": "日语",
    "English (US)": "英语（美国）",
    "Auto Compare": "自动比较",
    "Automatic": "自动",
    "Packaged Worker": "内置 Worker",
    "Development Python": "开发 Python",
    "Custom Executable": "自定义可执行文件",
    "Unknown": "未知",
    "Ready": "就绪",
    "Running": "运行中",
    "Missing": "缺失",
    "Error": "错误",
    "Draft": "草稿",
    "Queued": "排队中",
    "Recognized": "已识别",
    "Baked": "已烘焙",
    "Stale": "需要更新",
    "Valid": "有效",
    "Warning": "警告",
    "Unscanned": "未扫描",
    "Playback volume of the owned sequencer audio strip": (
        "插件预览音轨的播放响度"
    ),
    "Multiplier applied when baking mouth animation": "烘焙口型动画时应用的强度倍数",
    "Add an MMD model profile": "添加一个 MMD 模型配置",
    "Remove the selected MMD model profile": "删除选中的 MMD 模型配置",
    "Add a speech clip to the selected model": "为选中模型添加语音片段",
    "Delete the selected clip and all output owned by it": (
        "删除选中片段及其所属的动画和预览音轨"
    ),
    "Register a local Vosk language model": "注册本地 Vosk 语言模型",
    "Remove the last registered Vosk model": "删除最后注册的 Vosk 模型",
    "Check the bundled speech runtime": "检查内置语音运行环境",
    "Recognize the selected clip without blocking Blender": (
        "在不阻塞 Blender 的情况下识别选中片段"
    ),
    "Find MMD A, I, U, E, O, and optional closed-mouth shape keys": (
        "查找 MMD 的 A、I、U、E、O 和可选闭口形态键"
    ),
    "Recognize audio when needed, then generate MMD mouth animation": (
        "需要时先识别音频，然后生成 MMD 口型动画"
    ),
    "Replace the selected clip's generated mouth animation": (
        "替换选中片段已生成的口型动画"
    ),
    "Remove animation assets owned by the selected clip": (
        "移除选中片段所属的动画资源"
    ),
    "Cancel the running recognition task": "取消正在运行的识别任务",
}


def _catalog() -> dict[tuple[str, str], str]:
    result = {}
    for source, translated in _ZH_HANS.items():
        result[("*", source)] = translated
        result[("Operator", source)] = translated
    return result


TRANSLATIONS = {"zh_HANS": _catalog()}


def register() -> None:
    bpy.app.translations.register(_DOMAIN, TRANSLATIONS)


def unregister() -> None:
    try:
        bpy.app.translations.unregister(_DOMAIN)
    except (RuntimeError, ValueError):
        pass


__all__ = ["register", "unregister"]
