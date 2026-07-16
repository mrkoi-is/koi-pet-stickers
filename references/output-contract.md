# 输出契约

创建完整标准包、manifest 或验证报告前，先读本文件。

## 默认轻量交付

- 一张包含正好 16 个表情的 `4×4` 原始大图；
- 16 张固定方形透明 PNG；
- 一张可见棋盘格透明预览；
- 文字是可选的；有文字时由图像模型原生生成，本地脚本不得添加、替换或重排；
- 保留角色、已计划文字、白毛、文字描边和贴纸白边；
- 文件顺序使用 [grid-prompt-template.md](grid-prompt-template.md) 定义的固定 16 表情 row-major 映射。

推荐目录：

```text
work/
├── redskill-burst-16.png
├── transparent-cells/
│   ├── 01-happy.png
│   ├── …
│   └── 16-bye.png
└── transparent-preview.png
```

默认轻量交付用于小红书 / REDSkill 展示和聊天预览，不代表任何平台一定接受当前尺寸。需要微信投稿资产时，按 [wechat-specifications.md](wechat-specifications.md) 另行导出。

## 完整标准包

- 数量：正好 16 张；
- 格式：PNG；
- 画布：`1024×1024`；
- 背景：透明；
- 透明门槛：至少 10% 画布为完全透明；可见内容不触碰画布边缘，不能是透明边框包围的不透明矩形底板；
- 元数据：无 EXIF、GPS、ICC profile 或 PNG text chunks；
- 内容：无 logo、水印、场景、地面阴影、对话气泡或未计划文字；
- 文件名：`sticker-01.png` 至 `sticker-16.png`；
- 附件：manifest、机器 QA 报告和 contact sheet。

完整标准包是平台中性的 master，不等于微信投稿尺寸。

## 输入 job manifest

保存 UTF-8 JSON。`file` 相对 `--input-dir`，指向已经透明化、至少 10% 画布完全透明、可见内容不触边、包含计划文字或明确无字并通过视觉检查的 RGBA PNG；不透明白底图或透明边框包围的不透明矩形底板不能进入完整标准包。

`schema_version: 2` 将“表达的语义”与“画面中真正出现的文字”分开：

```json
{
  "schema_version": 2,
  "pet_name": "团子",
  "photo_grade": "A",
  "style_id": "bold-ink-caricature",
  "text_policy": "style-native",
  "stickers": [
    {
      "index": 1,
      "id": "happy",
      "semantic": "开心",
      "rendered_text": null,
      "file": "01-happy.png"
    }
  ]
}
```

`semantic` 是稳定的中文语义标签，用于保留 16 个 ID 的产品语义；它不要求画面一定出现中文。`rendered_text` 是画面中应原生生成的精确字符串，可使用任意语言；无文字时必须为 `null`，不得用空字符串代替。

`text_policy` 取值：

- `style-native`：由风格决定哪些格有字、哪些格无字；
- `all`：16 格都显示稳定中文语义，每格 `rendered_text` 必须等于 `semantic`；
- `none`：16 格全部无字，每格 `rendered_text` 必须为 `null`；
- `custom`：按用户计划混合使用精确文字与 `null`。

要求：

- 正好 16 条，序号覆盖 `1..16`；
- `id`、`semantic` 和顺序与固定 16 表情映射完全一致；
- `rendered_text` 必须是非空字符串或 `null`，并与 `text_policy` 一致；
- `file` 唯一且不能越出输入目录；
- `photo_grade` 为 `A` 或 `B`；
- `style_id` 为 `q-cute-handdrawn`、`flat-emoji`、`bold-comic`、`crayon-journal`、`naive-ink-watercolor` 或 `bold-ink-caricature`。

### schema v1 兼容

旧 `schema_version: 1` 继续可用：每格 `text` 同时视为稳定 `semantic` 和已渲染 `rendered_text`，整份任务等价于 `text_policy: all`。新任务优先使用 schema v2；在 schema v2 中，每格仍可用旧 `text` 作为 `semantic` 的兼容别名，但必须显式提供 `rendered_text`。若同时提供 `semantic` 和 `text`，两者必须相同。

## 脚本接口

```text
finalize.py --input-dir DIR --manifest FILE --output-dir DIR
validate.py --input-dir DIR [--manifest FILE] [--report FILE]
```

脚本必须：

- 非交互并支持 `--help`；
- 接受相对或绝对路径；
- 不修改源图；
- 输入源图、job manifest、master、预览、delivery manifest 和 QA report 的路径必须彼此不同；Unicode 等价名、大小写别名、符号链接或硬链接也视为碰撞；
- 同样输入重复运行时输出字节一致；
- stdout 只输出一个 JSON 结果，stderr 输出诊断。

退出码：

- `finalize.py`：`0` 成功，`2` 参数或 manifest 错误，`3` 源资产错误，`4` 处理错误；
- `validate.py`：`0` 通过，`2` 参数或 manifest 错误，`4` 报告处理错误，`5` 完成验证但存在失败检查。

## 标准输出树

```text
output/
├── master/
│   ├── sticker-01.png
│   ├── …
│   └── sticker-16.png
├── preview/
│   └── contact-sheet.png  # 以可见棋盘格展示透明边缘
├── manifest.json
└── qa-report.json
```

`manifest.json` 记录宠物名字、照片等级、风格、画布、`text_policy`、稳定 ID、`semantic`、`rendered_text`、源图 hash、输出 hash 和预览 hash。只对非 `null` 的 `rendered_text` 生成视觉文字 QA 警告；机器不会用 OCR 代替人工审字。不要写时间戳或绝对机器路径。

## 降级规则

本地打包或验证不能运行时，只交付原始大图、透明单格和透明预览，并明确标记为 `preview-only`。不要创建不完整的标准输出树，也不要称为完整标准包。
