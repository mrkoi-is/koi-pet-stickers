# 通用宠物宫格提示词模板

生成任何多表情宫格前先读本文件。运行时提示词只能使用当前宠物照片作为身份依据；风格预设决定怎么画，16 个稳定语义决定要表达什么，不再规定一套通用动作。

## 运行时字段

- `PET_NAME`：用户提供的宠物名字。
- `IDENTITY_LOCK`：按显著度列出 3–6 个身份锚点，只写照片中清楚可见、缩小后仍可辨认的结构和色块。品种名不能代替可见锚点。
- `IDENTITY_CHECKSUM`：把最关键的 3–4 个高显著结构压缩成一行逐格复核码，至少包含物种原生头部结构、耳型结构 / 耳根连接或不对称、吻部 / 喙及主色 / 高显著色块。
- `EAR_MORPHOLOGY_LOCK`：锁定耳朵数量、耳根连接、先天耳型、相对长度和高显著耳部花纹；同时明确动态耳姿可变，包括向侧后方展开的飞机耳、向后贴近头部的背耳、前倾、放松下沉、单耳转向和由透视产生的缩短 / 遮挡。合理耳姿不是身份漂移；“飞机耳 / 背耳”只是外观别名，运行时必须写侧向 / 外向或向后 / 贴头的几何变化，不能跨物种套模板。
- `UNCERTAINTY_LOCK`：未见区域可按当前物种的正常结构、正常肢体数量、主色和已知大色块保守补全，但不得虚构特殊花纹、配饰或新的身份锚点。
- `POSE_SCOPE`：允许头部、半身或全身；所有表达必须由当前物种原有结构完成。参考照片只锁定可见身份锚点，不限制构图范围。
- `STYLE_LOCK`：逐字带入所选预设的硬约束（“硬约束”字段），再加入最多两条当前宠物的风格化身份翻译。
- `COMPOSITION_PROFILE`：从 `face-first`、`balanced`、`action-first` 中选择所选预设声明的构图档。
- `COMPOSITION_LOCK`：逐字带入所选预设的“构图策略”；它决定裁切、头身比、尺度、脸部 / 身体权重和语义表达方式。
- `TEXT_POLICY`：`style-native`、`all`、`none` 或 `custom`。用户明确指定时优先；未指定时使用当前预设的默认文字策略。
- `TEXT_LANGUAGE`：计划文字的语言；无字时为 `NONE`。未指定且预设需要文字时默认简体中文。
- `CAPTION_LOCK`：逐字带入所选预设的“文字层级”和“文字排版”。
- `RENDERED_TEXT_PLAN`：16 个稳定 ID 各自对应一个精确字符串或 `NONE`。只有这里列出的字符串允许出现在图里。
- `EXTRACTION_LOCK`：逐字带入所选预设的“提取兼容”，说明最外层包络、断开组件、白边和网格归属。
- `ANTI_STYLE_LOCK`：逐字带入所选预设的“反风格”，用于阻止模型回落到通用 Q 萌模板。
- `GRID_SPEC`：固定 `4×4`、row-major 顺序、格子映射、gutter 和安全边距。
- `CELL_SEMANTICS`：16 个稳定 ID、内部中文语义标签和情绪方向。它不是动作清单，也不是可见文字清单。
- `BACKGROUND_LOCK`：统一纯白色（#FFFFFF）背景。
- `REFERENCE_ROLE_LOCK`：规范化宠物照片是唯一身份依据；可选风格参考只控制线重、色彩覆盖、留白、材质、夸张强度和文字笔触，不得贡献角色、物种、花纹、配饰、文字、道具、姿势、布局或背景。

所有动作遵守当前物种结构，优先使用头部、躯干、自然前肢、翅膀、鳍、尾巴、歪头、身体倾斜、姿态或表情。禁止人手、五指、握拳、比赞、OK 手势、敬礼、合十和人形挥手；不得补造肢体。补全正常身体不算补造肢体，但必须符合当前物种的正常结构与正常肢体数量。

## 决策优先级

提示词冲突时按以下顺序裁决：

1. 身份与交付不变量：同一宠物、物种结构、耳型结构、4×4、纯白背景、可分离 gutter 和计划文字准确性；
2. 所选风格运行契约：`STYLE_LOCK`、`COMPOSITION_LOCK`、`CAPTION_LOCK`、`EXTRACTION_LOCK`、`ANTI_STYLE_LOCK`；
3. `CELL_SEMANTICS` 的情绪方向；
4. 道具、姿势和情绪装饰；
5. 微纹理。

Style composition has higher priority than literal full-body action staging. 只要情绪清楚，模型可用脸部变形、裁切、姿势、物种原生动作、一个道具或贴近符号自由表达；不要为了统一动作而牺牲风格。

## 首轮提示词预检

调用图像生成前逐项检查；发现冲突就改提示词，不要先生成再靠第二版修复：

- 只存在一个 `style_id` 和一套线条 / 色彩 / 阴影语言；
- 所选预设的构图档、构图策略、文字策略、提取兼容和反风格已经全部填入对应运行字段；
- `IDENTITY_CHECKSUM` 是一行可画出的结构与色块校验码，没有“可爱、蓬松、某品种感”等套话；
- `EAR_MORPHOLOGY_LOCK` 已把先天耳型结构与动态耳姿分开，没有把参考照片中的瞬时耳位写成永久模板；
- 如果预设禁止真实纹理，身份词已经翻译为 outer-silhouette volume、大轮廓起伏或闭合色块；
- `RENDERED_TEXT_PLAN` 与 `TEXT_POLICY` 一致；`NONE` 格没有任何文字要求，非空格只有一个精确字符串；
- `CELL_SEMANTICS` 只写情绪和可选语义线索，没有强制 16 个统一全身动作；
- 身份锁、风格锁、纯白背景、安全区和提取兼容之间没有矛盾；
- 所选预设的“风格指纹”和“首轮抗漂移”已经带入，不只写显示名称。

## 运行时提示词骨架

```text
Use case: stylized-concept
Asset type: multi-expression pet chat-sticker sheet

Primary request:
Create a {{GRID_SPEC}} sticker sheet for the pet named “{{PET_NAME}}” on one exact 1:1 square canvas. Treat all cells as one coherent character series: same individual pet, same identity anchors, same palette, same drawing method, and same style family. The selected style may intentionally vary crop, head-to-body ratio, caricature distortion, and scale.

References:
Reference role lock:
{{REFERENCE_ROLE_LOCK}}
ORIGINAL PET IDENTITY: the normalized photos of the current pet are the sole identity authority for anatomy, markings, and palette.
OPTIONAL STYLE REFERENCES: use only for high-level line weight and rhythm, paint coverage, negative-space ratio, texture, caricature intensity, caption brush character, and silhouette language. Never copy or import their characters, species, markings, accessories, captions, props, poses, layout, background, or protected IP.

Identity lock:
{{IDENTITY_LOCK}}
Preserve every ranked identity anchor whenever that anchor is visible and judgeable. Translate each anchor into a style-compatible invariant before drawing: silhouette family, ear morphology and root attachment or species-native head structure, eye spacing or eye surround, muzzle/beak placement, color-block map, and high-salience asymmetry. A reasonable crop, foreshortening, head turn, or occlusion may make an anchor unjudgeable; record that case as N/A-occluded rather than inventing the feature or forcing a frontal view.

Identity checksum:
{{IDENTITY_CHECKSUM}}
Before drawing each cell, reapply this same checksum to all visible and judgeable structures. Never contradict a visible checksum item by mirroring asymmetry, replacing congenital ear/head topology, replacing the muzzle/beak, or substituting a generic color map. Do not expose or frontally restage every anchor merely to make it auditable.

Ear morphology lock:
{{EAR_MORPHOLOGY_LOCK}}
Keep ear count, root attachment, congenital pinna type, resting pinna-length category, stable asymmetry, and high-salience ear markings whenever visible. Dynamic ear carriage is expressive and may change when anatomically plausible: lateral/outward or lowered airplane-like carriage, pinned-back carriage, forward attention, relaxed lowering, one-ear turns, head-tilt foreshortening, or partial occlusion. Airplane-like carriage rotates, spreads, or lowers laterally/outward while retaining the same root and pinna; pinned-back carriage rotates toward and lies closer to the skull. Projected length may shorten with pose, perspective, or caricature without changing congenital length. 合理耳姿不是身份漂移；only an actual ear morphology substitution is identity drift.

Uncertainty lock:
{{UNCERTAINTY_LOCK}}

Pose scope:
{{POSE_SCOPE}}

Style runtime contract:
Style lock:
{{STYLE_LOCK}}
Composition profile:
{{COMPOSITION_PROFILE}}
Composition lock:
{{COMPOSITION_LOCK}}
Text policy and language:
{{TEXT_POLICY}}
{{TEXT_LANGUAGE}}
Caption lock:
{{CAPTION_LOCK}}
Extraction lock:
{{EXTRACTION_LOCK}}
Anti-style lock:
{{ANTI_STYLE_LOCK}}

Rendering priority:
delivery and identity invariants first; unmistakable selected style and composition second; semantic emotion third; optional pose, prop, and accents fourth; micro-texture last.

Grid and composition:
{{GRID_SPEC}}
Use sixteen equal square cells in row-major order. Treat each cell as one compact same-cell sticker cluster containing one pet character, allowed attached accents, and only the planned text for that cell. Keep every complete cluster visually separated from its neighbors by a broad, continuous pure-white corridor. Aim for generous breathing room around each cluster, but prioritize unambiguous row/column ownership and complete extractability over an exact percentage or perfect centering. The caption or a small accent may remain disconnected, but every component must clearly belong to the same cell and remain closer to its own pet than to any neighboring cluster. Draw no visible dividers, panels, frames, scene backgrounds, floor planes, or cross-cell elements.

Cell semantics:
{{CELL_SEMANTICS}}
These entries define stable IDs and emotions, not mandatory actions, crops, or poses. Style composition has higher priority than literal full-body action staging. Convey each emotion clearly using the selected style's own visual grammar.

Species-safe expression:
Adapt expression to the pet's real species anatomy. Use head angle, torso posture, natural forelimbs, wings, fins, tail, lean, compression, facial expression, one action-bound prop, or attached emotion accents. Do not draw human hands, fingers, palms, fists, thumbs-up, OK gestures, salutes, prayer hands, or human-like waving. Do not invent limbs.
Ear carriage may support emotion and visual rhythm when anatomically plausible. Distinguish dynamic airplane ears and pinned-back ears from congenital ear morphology; preserve root attachment and pinna type while allowing rotation, lowering, foreshortening, partial occlusion, and style-native asymmetry. 单一耳位不能独立判定情绪；read ears together with eyes, mouth, head and torso, tail or wings, and context.
Emotion accents may be freely chosen: tears, sweat, blush, motion lines, question or exclamation marks, ellipses, hearts, stars, anger marks, sleep symbols, or arrows. Do not treat expressive symbols as a checklist or as a source-QA failure.
Do not repeat one straight-on face template; the same straight-on contour may appear in no more than four cells. Adjacent cells and semantically similar reactions must differ in at least two visual dimensions chosen by the style: crop, head angle, gaze, facial deformation, body compression, direction, species-native limb/tail position, prop interaction, or outer silhouette.

Rendered text plan:
{{RENDERED_TEXT_PLAN}}
Render text according to the selected caption lock. A non-empty planned string must appear exactly once in its matching cell and in the requested language. A `NONE` cell must contain no letters, words, numbers, captions, pseudo-writing, or decorative glyph-like marks—including Zzz, ZZZ, Hi, OK, SOS, initials, and letter-shaped sleep sounds. Non-lexical emotion marks such as ?, !, hearts, stars, arrows, tears, sweat, blush, and motion lines remain allowed when they support the emotion and stay inside the safe area. Do not add translations, duplicated text, logos, watermarks, or unplanned writing. Place any planned text according to the selected caption lock and fully inside the safe area.

Background:
{{BACKGROUND_LOCK}}
Use one uniform pure white (#FFFFFF) canvas background. No off-white, cream, gray, warm-paper color, special key color, transparency request, texture, gradient, lighting variation, reflection, cast shadow, contact shadow, or watermark.

Avoid:
identity drift; species drift; ear morphology substitution; changed visible markings; mirrored stable asymmetry; copied reference characters or layouts; generic breed template substitution; duplicated emotional performance; mandatory full-body staging; human hands or gestures; extra limbs; cropped ears, wings, fins, paws, tail, planned text, prop, or accent; grid-line contamination; logos; watermarks; unplanned writing. Do not ban expressive airplane ears or pinned-back ears merely because they differ from the reference photo's momentary carriage.
```

说明：英文标签只用于稳定结构理解；身份、情绪和计划文字可使用用户语言。无字格必须真正无字。

## 固定 16 表情语义

`redskill-burst-16` 固定 16 个稳定 ID 和内部中文语义标签，便于文件命名、顺序和交付。以下“语义线索”只是可选方向，不是规范动作；最终构图服从所选风格。

| 序号 | 稳定 ID | 内部中文语义标签 | 情绪方向 | 语义线索（非动作规范） |
| ---: | --- | --- | --- | --- |
| 01 | `happy` | 开心 | 明亮、打开、愉悦 | 欢快目光、上扬节奏或庆祝符号 |
| 02 | `received` | 收到 | 明确回应、专注 | 点头感、确认感或短促回应 |
| 03 | `angry` | 生气 | 漫画怒气、不攻击 | 压缩、皱眉、怒气线或强对比 |
| 04 | `wronged` | 委屈 | 低落、受伤、克制 | 低垂目光、泪滴或缩起感 |
| 05 | `good-morning` | 早安 | 清醒、温暖、开始 | 明亮色点、舒展感或太阳符号 |
| 06 | `good-night` | 晚安 | 困倦、安静、结束 | 闭眼、哈欠、蜷缩或睡眠符号 |
| 07 | `thanks` | 谢谢 | 真诚、温和、感谢 | 柔和目光、低头感或贴近装饰 |
| 08 | `hug` | 抱抱 | 亲近、安慰、拥抱感 | 前倾、靠近、包围形或爱心 |
| 09 | `cheer-up` | 加油 | 鼓励、向前、振奋 | 前倾节奏、上扬尾 / 翅或冲击线 |
| 10 | `okay` | 好的 | 同意、确认、轻快 | 点头感、稳定目光或确认符号 |
| 11 | `no` | 不行 | 拒绝、坚定、边界 | 侧开、后缩、摇头感或阻挡符号 |
| 12 | `question` | 怎么啦 | 关切、疑问、倾听 | 歪头、错位目光或问号 |
| 13 | `eating` | 吃饭啦 | 期待、进食、满足 | 食物、碗或靠近食物的神态 |
| 14 | `miss-you` | 想你啦 | 想念、依恋、柔软 | 贴近、抱尾、远望或爱心 |
| 15 | `rush` | 冲鸭 | 冲劲、速度、行动 | 强方向、拉长节奏或速度线 |
| 16 | `bye` | 拜拜 | 告别、离开、回望 | 转身、回头、尾部节奏或挥别感 |

## 唯一 4×4 宫格规格

```text
Exactly sixteen equal cells in a 4×4 arrangement, row-major order.
Row 1: 01-happy/开心, 02-received/收到, 03-angry/生气, 04-wronged/委屈.
Row 2: 05-good-morning/早安, 06-good-night/晚安, 07-thanks/谢谢, 08-hug/抱抱.
Row 3: 09-cheer-up/加油, 10-okay/好的, 11-no/不行, 12-question/怎么啦.
Row 4: 13-eating/吃饭啦, 14-miss-you/想你啦, 15-rush/冲鸭, 16-bye/拜拜.
Use an exact 1:1 square canvas. In every cell, place one compact same-cell sticker cluster with generous pure-white breathing room.
Keep broad, continuous pure-white corridors between all rows and columns so every cluster can be assigned and extracted independently; exact per-side percentages are guidance, not an acceptance gate.
```
