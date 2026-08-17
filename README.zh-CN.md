# MMD Mouth

[English](README.md) | [简体中文](README.zh-CN.md)

MMD Mouth 是一个适用于 Blender 5.2 的插件，可以把离线语音识别结果转换为
MMD `A/I/U/E/O` 嘴型动画。

## 功能

- 一键执行“生成口型”：需要时先识别，再烘焙动画。
- 内置中文、日语和美式英语 Vosk 小型模型压缩包。
- 用户端不需要安装 Python、pip、命令行工具或手动配置模型目录。
- 支持中文拼音、日语 OpenJTalk 和英语 CMUdict G2P。
- 使用统一 IPA 音素和带辅音处理的 `REST/CLOSED/A/I/U/E/O` 时间线。
- 对双唇音 `p/b/m` 自动加入闭嘴过渡并抑制元音。
- 自动查找 MMD `あ/い/う/え/お` 形态键和可选的 `口閉じ` 形态键。
- 支持直接写入形态键的 `BAKE` 模式，以及控制器属性 `DRIVER` 模式。
- 每个片段独立拥有 Action 和 NLA Strip，并支持安全清理。
- 自动管理带有片段起始帧、裁剪、时长和音量同步的 VSE 预览音轨。
- 每个片段可单独设置混入、混出过渡时间，并使用限幅平滑曲线输出。
- 可展开、按起始时间自动排序、支持手动编辑的口型时间线。
- 使用 Blender 内置能力将常见音频转换为缓存的 16-bit PCM WAV。
- 支持线性、平滑步进、正弦、缓入和缓出等嘴型混合模式。
- 支持英文和简体中文 Blender 界面本地化。

## 安装和使用

1. 在 Blender 5.2 中安装 `dist-addon/MMDmouth-0.5.0.zip` 插件。
2. 打开 `3D 视图 > 侧栏 > MMD Mouth`。
3. 选择 MMD 模型根对象并添加模型条目。
4. 添加口型片段，选择 WAV 文件、语言、起始帧和输出模式。
5. 点击 `Generate Mouth`。
6. 展开 `Mouth Timeline`，逐项调整嘴型、开始时间、结束时间或权重。
7. 点击 `Regenerate`，使用调整后的时间线重新烘焙，不会再次运行识别。

`Audio` 旁边的刷新按钮可以把 Blender 支持的常见格式（例如 MP3、OGG、FLAC 和非
PCM WAV）转换为缓存的 16-bit PCM WAV。点击 `Generate Mouth` 时，如果识别需要，
插件也会自动执行同样的转换。

当片段没有可用时间线，或识别输入已经过期时，`Generate Mouth` 会运行语音识别。
`Regenerate` 始终读取当前可编辑的时间线，因此手动修正的时间不会被 Vosk 结果覆盖。

首次使用时，插件会在 Blender 用户数据目录的 `mmd_mouth/models` 下检查并解压所选
Vosk 模型。插件不会向 Blender 安装目录写入模型数据。

worker 读取未压缩的 16-bit PCM WAV，支持单声道和立体声；立体声会在 worker 中转换为
单声道。Blender 内置音频解码器会在识别前把支持的压缩格式转换为缓存的单声道 PCM WAV。

`Auto Compare` 会让所有启用的语言模型识别整个片段，并保留评分最高的候选结果。它
适合语言未知的音频，但不是按片段进行的混合语言识别或语言自动路由。

## 开发

- [数据模型](docs/DATA_MODEL.md)
- [开发指南](docs/DEVELOPMENT.md)
- [Vosk 模型和 worker](docs/VOSK.md)

使用 `build_worker.ps1` 构建 worker，再通过
`build_addon.ps1 -SkipWorkerBuild` 创建 Blender 安装压缩包。
