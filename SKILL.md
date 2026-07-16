---
name: koi-pet-stickers
description: "Mr.Koi 原创宠物表情 Skill：把一张宠物照片和名字直接生成适合小红书 REDSkill 展示的 4×4、16 格宠物 IP 表情大图，并提取为 16 张透明 PNG。内置六种风格，适用于制作、优化、裁切、透明化、验证和交付宠物表情包。"
---

# Mr.Koi · 宠物 IP 表情工坊

> 作者：Mr.Koi · 版权所有 © 2026 Mr.Koi
> 个人及非商用免费；任何商业使用、转售、集成或代客服务均须取得书面授权。
> 完整条款见 [LICENSE](LICENSE)，签约模板见
> [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)，商用联系：i@mrkoi.is。

## 品牌身份

- 技术名称与调用名：`koi-pet-stickers` / `$koi-pet-stickers`。
- 中文展示名：`Mr.Koi · 宠物 IP 表情工坊`。
- 核心口号：`一张照片，六种风格，16 张透明表情`。
- 品牌署名保留在 Skill、授权文件和发布介绍中；未经用户明确要求，不在用户生成的表情图片里添加 Mr.Koi 水印、Logo 或宣传文字。

使用一张宠物照片和一个名字，一次生成 16 个宠物表情。默认采用 `q-cute-handdrawn`（Q萌手绘贴纸）；不要求用户填写问卷、补图或选择模式。用户已上传同一宠物的多张照片时，可共同用于身份锁定。

## 产品边界

- 只做单个宠物角色，不加入人物、周边 mockup、漫画剧情、视频、模型训练、自动投稿或第三方图像服务。
- 默认交付一张采用风格原生文字策略的 `4×4` 大图、16 张透明 PNG 和一张透明棋盘格预览。
- 默认验收只阻断切图失败：只要脚本成功输出 16 张完整、无邻格污染的透明 PNG，就继续交付；身份、风格、情绪、动作和文字效果只记录为非阻断观察。
- 只有用户明确要求企业级完整包时，才额外交付 `1024×1024` master、manifest 和机器验证报告。
- 平台规格只作为导出参考，不承诺平台审核一定通过。

## 按需阅读

1. 生成前完整阅读当前 `$imagegen` 技能。
2. 分析照片前阅读 [references/identity-and-style.md](references/identity-and-style.md)。
3. 锁定风格前阅读 [references/style-presets.md](references/style-presets.md)。
4. 组装提示词前阅读 [references/grid-prompt-template.md](references/grid-prompt-template.md)。
5. 展示或交付前阅读 [references/qa-rubric.md](references/qa-rubric.md)。
6. 只有创建完整标准包时才阅读 [references/output-contract.md](references/output-contract.md)。
7. 只有用户询问微信投稿或平台衍生资产时才阅读 [references/wechat-specifications.md](references/wechat-specifications.md)。

## 生成边界

- 只使用内置 `$imagegen` / `image_gen` 生成图片。
- 不调用外部图像服务，不索要或使用 API Key，不运行生成 CLI，不切换或硬编码模型，不配置备用生成路径。
- 不使用绿幕或特殊 key 色。源图固定纯白色（#FFFFFF）背景，只允许本地脚本做边缘连通白底透明化。
- 可见文字不是必选项。若 `RENDERED_TEXT_PLAN` 计划了文字，只让图像模型在对应格原生绘制；本地脚本只能裁切、透明化、缩放、去元数据、打包和验证，不能添加、替换或重排文字。
- 调用内置图像工具时，保存当前运行键：`store("pet-sticker:" + RUN_ID, result)`，并用 `generatedImage(result)` 回传；不要遍历返回结构猜测图片位置。
- 长任务结束后只看到 `Script completed` 或空文本输出不等于生成失败。先用 `load("pet-sticker:" + RUN_ID)` 恢复并再次执行 `generatedImage(result)`，再检查当前任务的 `$CODEX_HOME/generated_images/` 是否出现新图片。不得在结果恢复检查完成前发起第二次生成。
- 只有缓存结果和已保存的新图片都不存在时，才允许只重试同一请求一次，且提示词与参考图完全相同；再次失败就暂停并说明限制。

## 唯一工作流

1. 创建当前任务独立目录：

   `RUN_DIR=work/koi-pet-stickers-runs/<宠物名>-<style_id>-<任务 ID 或时间戳>`

   优先使用任务 ID，拿不到时用精确到秒的时间戳。不得复用其他任务、宠物或历史失败结果的目录。规范化用户上传的 1–3 张同一宠物照片；一张清晰照片已经足够，不主动索要补图：

   ```bash
   uv run --script scripts/prepare_references.py \
     --input /path/to/pet-photo.jpg \
     --output-dir "$RUN_DIR/references"
   ```

   宠物照片是唯一身份依据。用户主动提供的风格参考只控制线重、色彩覆盖率、留白、材质和夸张语言，不得贡献角色、物种、花纹、配饰、文字、道具、姿势、布局或背景。

2. 从照片提取 3–6 个缩小后仍可辨认的身份锚点和不确定项，再压缩成一行 `IDENTITY_CHECKSUM`。至少覆盖物种结构、耳型结构 / 耳根连接或不对称、吻部 / 喙及主色地图；品种名不能代替可见特征。另写 `EAR_MORPHOLOGY_LOCK`：锁定耳朵数量、耳根连接、先天耳型、静息耳廓长度级别、稳定不对称和高显著耳部花纹，但允许物种合理的飞机耳、背耳、前倾、放松下沉、单耳转向和透视遮挡。参考照片只锁定身份，不限制头部、半身或全身构图；未见区域按当前物种正常结构、正常肢体数量和已知大色块保守补全，不虚构高显著隐藏花纹。

3. 锁定一个风格。用户未指定时使用 `q-cute-handdrawn`；也支持 `flat-emoji`、`bold-comic`、`crayon-journal`、`naive-ink-watercolor`、`bold-ink-caricature`。从预设逐字填入构图档、构图策略、默认文字策略、文字层级、提取兼容和反风格，不得只写风格名称。

4. 按 [references/grid-prompt-template.md](references/grid-prompt-template.md) 生成运行提示词。固定的是同一宠物、16 个稳定语义、物种结构、耳型结构、纯白背景、可分离白色走廊和顺序；不固定统一动作、统一景别、统一角色尺度或参考照的瞬时耳位。情绪语义必须正确，模型可按所选风格用脸部变形、动态耳姿、景别、姿势、物种原生动作、道具或贴近角色的情绪符号自由表达。合理耳姿不是身份漂移。

   所有动作遵守当前物种结构，禁止人手、五指、握拳、比赞、OK 手势、敬礼、合十或补造肢体。允许按正常物种结构补全照片中未见的身体，但不能改变正常肢体数量。

   未指定文字时使用预设的风格原生策略：可以全有字、混合、稀疏或全无字；用户明确要求全中文、全无字、其他语言或自定义文案时优先。把 16 格真正要显示的精确字符串或 `NONE` 写入 `RENDERED_TEXT_PLAN`。无字格不得出现 `Zzz`、`Hi`、`OK` 等字母型拟声或伪文字，有字格只出现计划字符串；问号、爱心、泪滴和动作线等非词汇情绪符号仍可按语义自由使用。

5. 执行首轮预检：只有一套风格语言；身份质感已翻译为当前风格的轮廓 / 色块语言；`IDENTITY_CHECKSUM`、风格指纹、构图锁、文字锁和反风格已写入；没有通用动作模板反向覆盖风格。发现冲突只改提示词。调用生成前把最终提示词保存为 `$RUN_DIR/generation-prompt.txt`。

6. 一次生成一张正好 `4×4`、纯白背景的大图，保存为 `$RUN_DIR/attempt-01-source-sheet.png`。每格是一个处于安全区内、可独立裁切的同格表达簇；计划文字和小装饰可与角色像素断开，但必须明显属于本格并远离格线。恢复内置工具结果后复制文件到运行目录，不得只留在 `$CODEX_HOME/generated_images/`。

7. 正式选择源图前，先对每次尝试运行一次诊断提取，把脚本 JSON 和透明预览保存到 `$RUN_DIR/diagnostics/attempt-XX/`，并写入 `$RUN_DIR/source-qa.json`。默认 gate 只看切图结果：`extract_grid.py` 返回 `ok: true`、正好输出 16 张非空 RGBA PNG，且透明预览逐格确认角色、文字、耳朵、爪子、尾巴、白边、道具和装饰没有被裁掉或混入邻格，即可通过。`source_components_cross_grid`、`possible_neighbor_residue`、`component_owner_near_grid_line`、`source_safe_margin_below_ratio`、负 `source_margins` 和其他 warning 都保留为诊断线索，不再单独判失败；只有透明结果实际出现缺失、错格、邻格残片、白底方块或透明化误删时才是切图失败。身份、风格、情绪、动作、文字和耳姿只记录为非阻断观察。至少记录 `selected_attempt`、每次尝试文件名、脚本 `ok`、16 张输出计数、透明预览结论和 warnings。

8. 只有诊断提取实际失败时才允许整图修复一次；优先先调整提取参数重跑，确认问题来自源大图本身后，才把上一张大图作为布局参考重新生成。第二次保存为 `$RUN_DIR/attempt-02-source-sheet.png`，不得覆盖失败尝试。第二张仍无法完整切出 16 张就停止并说明；不单格补画、不拼接、不本地改字。把切图通过的尝试复制为 `$RUN_DIR/source-sheet.png`，并在 `source-qa.json` 更新 `selected_attempt`。

9. 提取透明单格：

   ```bash
   uv run --script scripts/extract_grid.py \
     --input-sheet "$RUN_DIR/source-sheet.png" \
     --output-dir "$RUN_DIR/transparent-cells" \
     --preview "$RUN_DIR/transparent-preview.png" \
     --rows 4 --cols 4 --min-cell-px 240 \
     --halo-px 2 --padding-px 22 \
     --filenames 01-happy.png,02-received.png,03-angry.png,04-wronged.png,05-good-morning.png,06-good-night.png,07-thanks.png,08-hug.png,09-cheer-up.png,10-okay.png,11-no.png,12-question.png,13-eating.png,14-miss-you.png,15-rush.png,16-bye.png
   ```

10. 阅读脚本 warnings 并逐格检查透明预览。warning 本身不阻断交付；只在透明结果确实误删、裁切、错格或混入邻格时判失败。透明化失败先重新提取；只有源图本身无法分离才使用上述一次整图修复机会。

11. 展示原始大图与透明预览，交付原始大图和 16 张透明 PNG。完成照片分析后直接继续，不询问用户选择数量或流程。

## 可选完整标准包

只有用户明确要求企业级完整交付、标准 master 或严格打包时，才按 [references/output-contract.md](references/output-contract.md) 创建 schema v2 manifest，并执行：

```bash
uv run --script scripts/finalize.py \
  --input-dir "$RUN_DIR/transparent-cells" \
  --manifest "$RUN_DIR/job-manifest.json" \
  --output-dir "$RUN_DIR/output"

uv run --script scripts/validate.py --input-dir "$RUN_DIR/output"
```

只有验证器返回 `0`、`qa-report.json` 为 `ok: true`，且人工视觉 QA 通过后，才称为完整标准包。

## 完成标准

- 默认交付：原始 `4×4` 大图、16 张透明 PNG、透明预览、`generation-prompt.txt` 和 `source-qa.json`。
- 完整标准包：再包含 16 张透明 `1024×1024` master、manifest、contact sheet 和通过的机器验证报告。
- 默认交付只要求 16 张透明 PNG 全部切图完整、顺序正确、无邻格残留和透明化误删；其他视觉差异记录在 `source-qa.json`，不阻断本阶段交付。
