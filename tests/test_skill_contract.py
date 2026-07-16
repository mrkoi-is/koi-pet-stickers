#!/usr/bin/env python3
"""Static regressions for the one-step pet sticker skill contract."""

from __future__ import annotations

import ast
import runpy
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
IDENTITY = (SKILL_DIR / "references" / "identity-and-style.md").read_text(
    encoding="utf-8"
)
STYLES = (SKILL_DIR / "references" / "style-presets.md").read_text(
    encoding="utf-8"
)
GRID_PROMPT = (SKILL_DIR / "references" / "grid-prompt-template.md").read_text(
    encoding="utf-8"
)
OUTPUT = (SKILL_DIR / "references" / "output-contract.md").read_text(
    encoding="utf-8"
)
QA = (SKILL_DIR / "references" / "qa-rubric.md").read_text(encoding="utf-8")
METADATA = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
LICENSE = (SKILL_DIR / "LICENSE").read_text(encoding="utf-8")
COMMERCIAL_LICENSE = (SKILL_DIR / "COMMERCIAL-LICENSE.md").read_text(
    encoding="utf-8"
)
README = (SKILL_DIR / "README.md").read_text(encoding="utf-8")
PIPI_EXAMPLE = (SKILL_DIR / "examples" / "pipi" / "README.md").read_text(
    encoding="utf-8"
)


class SkillContractTest(unittest.TestCase):
    def test_public_readme_and_pipi_example_contract(self) -> None:
        for required in (
            "# Mr.Koi · 宠物 IP 表情工坊",
            "https://github.com/mrkoi-is/koi-pet-stickers.git",
            "$koi-pet-stickers",
            "examples/pipi/README.md",
            "六种风格",
            "[LICENSE](LICENSE)",
            "[COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)",
        ):
            self.assertIn(required, README)

        for required in (
            "# 皮皮：六风格完整示例",
            "assets/input-pipi.jpg",
            "q-cute-handdrawn",
            "Q萌手绘贴纸",
            "极简扁平 Emoji",
            "粗线漫画大字",
            "蜡笔手帐涂鸦",
            "稚拙墨线水彩",
            "粗墨怪萌水彩",
            "正好 16 张非空 RGBA PNG",
        ):
            self.assertIn(required, PIPI_EXAMPLE)

        example_assets = {
            path.name
            for path in (SKILL_DIR / "examples" / "pipi" / "assets").iterdir()
            if path.is_file()
        }
        self.assertEqual(
            example_assets,
            {
                "input-pipi.jpg",
                "q-cute-handdrawn.png",
                "flat-emoji.png",
                "bold-comic.png",
                "crayon-journal.png",
                "naive-ink-watercolor.png",
                "bold-ink-caricature.png",
            },
        )

    def test_author_and_commercial_license_contract(self) -> None:
        self.assertEqual(SKILL_DIR.name, "koi-pet-stickers")
        for required in (
            "name: koi-pet-stickers",
            "# Mr.Koi · 宠物 IP 表情工坊",
            "作者：Mr.Koi",
            "版权所有 © 2026 Mr.Koi",
            "个人及非商用免费",
            "`koi-pet-stickers` / `$koi-pet-stickers`",
            "一张照片，六种风格，16 张透明表情",
            "不在用户生成的表情图片里添加 Mr.Koi 水印",
            "[LICENSE](LICENSE)",
            "[COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)",
            "i@mrkoi.is",
        ):
            self.assertIn(required, SKILL)

        for required in (
            "版权所有 © 2026 Mr.Koi",
            "Koi Pet Stickers 个人与非商用许可条款",
            "`koi-pet-stickers` Skill",
            "商业使用、转售、集成或代客服务",
            "须在使用前与 Mr.Koi 签署单独的书面",
            "i@mrkoi.is",
        ):
            self.assertIn(required, LICENSE)

        for required in (
            "授权类型",
            "授权地域",
            "授权期限",
            "授权费",
            "违约",
            "签名 / 盖章",
        ):
            self.assertIn(required, COMMERCIAL_LICENSE)

        self.assertIn("Mr.Koi · 宠物 IP 表情工坊", METADATA)
        self.assertNotIn("make-pet-ip-stickers", SKILL + LICENSE + COMMERCIAL_LICENSE + METADATA)

    def test_minimal_one_step_entry(self) -> None:
        for required in (
            "一张宠物照片和一个名字",
            "q-cute-handdrawn",
            "唯一工作流",
            "一张采用风格原生文字策略的 `4×4` 大图",
            "scripts/extract_grid.py",
            "16 张透明 PNG",
            "完成照片分析后直接继续",
        ):
            self.assertIn(required, SKILL)
        for removed in ("12 张", "IP母版", "IP 母版", "split_grid.py", "transparentize.py"):
            self.assertNotIn(removed, SKILL)

    def test_generation_boundary_is_builtin_only(self) -> None:
        for required in (
            "只使用内置 `$imagegen` / `image_gen`",
            "不调用外部图像服务",
            "不索要或使用 API Key",
            "不运行生成 CLI",
            "不切换或硬编码模型",
            "只重试同一请求一次",
            "不能添加、替换或重排文字",
        ):
            self.assertIn(required, SKILL)

        forbidden_imports = {
            "fal_client",
            "httpx",
            "openai",
            "replicate",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        for script in (SKILL_DIR / "scripts").glob("*.py"):
            tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
            imports = {
                node.names[0].name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
            }
            imports.update(
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
            self.assertFalse(imports & forbidden_imports, script.name)

    def test_builtin_generation_result_is_recovered_before_retry(self) -> None:
        for required in (
            "generatedImage(result)",
            "store(",
            "load(",
            "空文本输出不等于生成失败",
            "不得在结果恢复检查完成前发起第二次生成",
            "已保存的新图片",
        ):
            self.assertIn(required, SKILL)

    def test_every_task_uses_an_independent_run_directory(self) -> None:
        for required in (
            "RUN_DIR",
            "当前任务独立目录",
            "任务 ID",
            "时间戳",
            "不得复用其他任务",
        ):
            self.assertIn(required, SKILL)
        for shared_path in (
            "work/references",
            "work/redskill-burst-16.png",
            "work/transparent-cells",
            "work/transparent-preview.png",
            "--output-dir output",
        ):
            self.assertNotIn(shared_path, SKILL)
        self.assertIn("work/koi-pet-stickers-runs", SKILL)

    def test_grid_prompt_is_pet_agnostic_and_fixed_to_16(self) -> None:
        for field in (
            "PET_NAME",
            "IDENTITY_LOCK",
            "IDENTITY_CHECKSUM",
            "EAR_MORPHOLOGY_LOCK",
            "UNCERTAINTY_LOCK",
            "POSE_SCOPE",
            "STYLE_LOCK",
            "COMPOSITION_PROFILE",
            "COMPOSITION_LOCK",
            "TEXT_POLICY",
            "TEXT_LANGUAGE",
            "CAPTION_LOCK",
            "RENDERED_TEXT_PLAN",
            "EXTRACTION_LOCK",
            "ANTI_STYLE_LOCK",
            "GRID_SPEC",
            "CELL_SEMANTICS",
            "BACKGROUND_LOCK",
            "REFERENCE_ROLE_LOCK",
        ):
            self.assertIn(f"`{field}`", GRID_PROMPT)
        for anatomy in ("前肢", "翅膀", "鳍", "尾巴", "歪头"):
            self.assertIn(anatomy, GRID_PROMPT)
        for caption in (
            "01-happy/开心",
            "08-hug/抱抱",
            "12-question/怎么啦",
            "16-bye/拜拜",
        ):
            self.assertIn(caption, GRID_PROMPT)
        self.assertIn("Exactly sixteen equal cells in a 4×4 arrangement", GRID_PROMPT)
        self.assertNotIn("OPTIONAL REFERENCE", GRID_PROMPT)
        self.assertNotIn("柯基", GRID_PROMPT)

    def test_identity_checksum_and_style_fingerprint_remain_visual_guidance(self) -> None:
        for required in (
            "Identity checksum",
            "{{IDENTITY_CHECKSUM}}",
            "all visible and judgeable structures",
            "N/A-occluded",
        ):
            self.assertIn(required, GRID_PROMPT)
        for required in (
            "身份锚点矩阵",
            "风格指纹",
            "不能凭整体相似直接通过",
            "写实毛发侵入",
            "大面积完整铺色",
            "亮晶晶大眼",
        ):
            self.assertIn(required, QA)

    def test_style_registry_is_complete(self) -> None:
        expected = {
            "q-cute-handdrawn": "Q萌手绘贴纸",
            "flat-emoji": "极简扁平 Emoji",
            "bold-comic": "粗线漫画大字",
            "crayon-journal": "蜡笔手帐涂鸦",
            "naive-ink-watercolor": "稚拙墨线水彩",
            "bold-ink-caricature": "粗墨怪萌水彩",
        }
        registry = runpy.run_path(str(SKILL_DIR / "scripts" / "style_presets.py"))
        self.assertEqual(registry["DEFAULT_STYLE_ID"], "q-cute-handdrawn")
        self.assertEqual(
            {
                style_id: preset["display_name"]
                for style_id, preset in registry["STYLE_PRESETS"].items()
            },
            expected,
        )
        for style_id, style_name in expected.items():
            self.assertIn(style_id, STYLES)
            self.assertIn(style_name, STYLES)

    def test_identity_anchor_and_open_pose_contract(self) -> None:
        for document in (SKILL, IDENTITY, GRID_PROMPT):
            self.assertIn("3–6 个", document)
            self.assertIn("身份锚点", document)
            self.assertIn("品种名不能代替", document)
        for required in (
            "耳型结构",
            "耳根连接",
            "动态耳姿",
            "飞机耳",
            "背耳",
        ):
            self.assertIn(required, IDENTITY)
            self.assertIn(required, GRID_PROMPT)
        for required in (
            "允许头部、半身或全身",
            "参考照片只锁定可见身份锚点，不限制构图范围",
            "未见区域",
        ):
            self.assertIn(required, GRID_PROMPT)
        self.assertNotIn("风格预设不能扩大可见范围", GRID_PROMPT)
        self.assertNotIn("构图范围以照片可见范围为上限", IDENTITY)

    def test_species_safe_action_contract(self) -> None:
        self.assertIn(
            "所有动作遵守当前物种结构，禁止人手、五指、握拳、比赞、OK 手势、敬礼、合十或补造肢体",
            STYLES,
        )
        for forbidden_gesture in (
            "五指",
            "握拳",
            "比赞",
            "OK 手势",
            "敬礼",
            "合十",
            "不得补造肢体",
        ):
            self.assertIn(forbidden_gesture, GRID_PROMPT)
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, QA])
        for removed in (
            "受控拟人化手势",
            "漫画化比赞",
            "漫画化小拳头",
            "漫画化挥手",
        ):
            self.assertNotIn(removed, core)
        self.assertIn("补全正常身体不算补造肢体", GRID_PROMPT)

    def test_ear_morphology_is_locked_but_emotional_carriage_is_open(self) -> None:
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, QA])
        for required in (
            "合理耳姿不是身份漂移",
            "耳型结构替换",
            "飞机耳",
            "背耳",
            "单一耳位不能独立判定情绪",
        ):
            self.assertIn(required, core)
        for required in (
            "耳朵数量",
            "耳根连接",
            "先天耳型",
            "高显著耳部花纹",
        ):
            self.assertIn(required, QA)
        for removed in (
            "立耳必须始终竖直",
            "委屈只能通过眼神",
            "任一格把立耳改成垂耳",
        ):
            self.assertNotIn(removed, core)

    def test_occluded_identity_anchors_are_not_false_hard_failures(self) -> None:
        core = "\n".join([IDENTITY, GRID_PROMPT, QA])
        for required in (
            "N/A-occluded",
            "合理裁切",
            "多个清晰非遮挡视图",
            "visible and judgeable",
        ):
            self.assertIn(required, core)
        self.assertNotIn("Every one of the sixteen cells must preserve every checksum item", GRID_PROMPT)

    def test_projected_ear_length_is_not_congenital_length_change(self) -> None:
        core = "\n".join([IDENTITY, GRID_PROMPT, QA])
        for required in (
            "静息耳廓长度级别",
            "投影长度变化不等于",
            "Projected length may shorten",
        ):
            self.assertIn(required, core)

    def test_compact_square_grid_contract(self) -> None:
        for required in (
            "exact 1:1 square canvas",
            "one compact same-cell sticker cluster",
            "broad, continuous pure-white corridor",
            "exact percentage or perfect centering",
            "may remain disconnected",
            "according to the selected caption lock",
        ):
            self.assertIn(required, GRID_PROMPT)
        for removed in (
            "centered 60%",
            "at least 20% continuous pure-white margin",
            "--bleed-px",
        ):
            self.assertNotIn(removed, GRID_PROMPT + SKILL)

    def test_layout_diagnostics_run_before_source_selection(self) -> None:
        for required in (
            "source_components_cross_grid",
            "possible_neighbor_residue",
            "source_safe_margin_below_ratio",
            "source_margin_ratios",
            "负 `source_margins`",
            "诊断提取",
        ):
            self.assertIn(required, SKILL + QA)
        self.assertIn("warning 本身不阻断", QA)
        self.assertIn("不是自动失败条件", QA)

    def test_default_gate_is_successful_transparent_extraction(self) -> None:
        for required in (
            "默认验收只阻断切图失败",
            "`extract_grid.py` 返回 `ok: true`",
            "正好输出 16 张非空 RGBA PNG",
            "warning 本身不阻断交付",
            "身份、风格、情绪、动作、文字和耳姿只记录为非阻断观察",
        ):
            self.assertIn(required, SKILL)
        for required in (
            "默认切图硬失败",
            "只有实际透明结果失败才触发整图修复",
            "最终以 16 张透明 PNG 和棋盘格预览是否完整、顺序正确、互不污染为准",
        ):
            self.assertIn(required, QA)

    def test_pure_white_background_contract(self) -> None:
        for document in (SKILL, IDENTITY, STYLES, GRID_PROMPT, QA):
            self.assertIn("纯白色（#FFFFFF）", document)
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, QA])
        self.assertNotIn("极浅中性背景", core)
        self.assertNotIn("very light neutral background", core)

    def test_style_hard_constraints(self) -> None:
        self.assertEqual(STYLES.count("**硬约束：**"), 6)
        self.assertEqual(STYLES.count("**风格指纹：**"), 6)
        self.assertEqual(STYLES.count("**首轮抗漂移：**"), 6)
        for required in (
            "零纹理",
            "零渐变",
            "硬边阴影",
            "颗粒只在色块内部",
            "逐根毛丝",
            "45–60% 稀疏透明水彩",
            "至少 40% 轮廓内白纸",
            "拓扑闭合且不向背景泄露内部白纸",
            "狗鼻子跨物种套用",
            "水彩覆盖 20–40%",
            "默认至少 60% 轮廓内白纸",
            "小黑瞳",
            "不规则眼白",
            "深色身份色块",
            "主轮廓线宽约占单格宽度 1.5–2.5%",
        ):
            self.assertIn(required, STYLES)
        self.assertIn("逐字带入所选预设的硬约束", GRID_PROMPT)
        self.assertIn(
            "身份、情绪、风格、动作、耳姿、构图和文字效果差异",
            QA,
        )

    def test_every_style_has_a_complete_runtime_visual_contract(self) -> None:
        for field in (
            "**构图档：**",
            "**构图策略：**",
            "**默认文字策略：**",
            "**文字层级：**",
            "**提取兼容：**",
            "**反风格：**",
        ):
            self.assertEqual(STYLES.count(field), 6)
        for profile in ("`face-first`", "`balanced`", "`action-first`"):
            self.assertIn(profile, STYLES)

        registry = runpy.run_path(str(SKILL_DIR / "scripts" / "style_presets.py"))
        profiles = {
            style_id: preset["composition_profile"]
            for style_id, preset in registry["STYLE_PRESETS"].items()
        }
        self.assertEqual(
            profiles,
            {
                "q-cute-handdrawn": "balanced",
                "flat-emoji": "face-first",
                "bold-comic": "action-first",
                "crayon-journal": "balanced",
                "naive-ink-watercolor": "face-first",
                "bold-ink-caricature": "face-first",
            },
        )
        text_policies = {
            style_id: preset["default_text_policy"]
            for style_id, preset in registry["STYLE_PRESETS"].items()
        }
        self.assertEqual(
            text_policies,
            {
                "q-cute-handdrawn": "mixed",
                "flat-emoji": "none",
                "bold-comic": "all",
                "crayon-journal": "mixed",
                "naive-ink-watercolor": "sparse",
                "bold-ink-caricature": "sparse-or-none",
            },
        )

    def test_generic_prompt_defers_composition_and_caption_to_selected_style(self) -> None:
        for removed in (
            "same proportions",
            "same scale in every cell",
            "friendly Chinese lettering style",
            "caption must touch",
        ):
            self.assertNotIn(removed, GRID_PROMPT)
        for required in (
            "selected style may intentionally vary crop, head-to-body ratio, caricature distortion, and scale",
            "Style composition has higher priority than literal full-body action staging",
            "{{COMPOSITION_PROFILE}}",
            "{{COMPOSITION_LOCK}}",
            "{{TEXT_POLICY}}",
            "{{TEXT_LANGUAGE}}",
            "{{CAPTION_LOCK}}",
            "{{RENDERED_TEXT_PLAN}}",
            "{{EXTRACTION_LOCK}}",
            "{{ANTI_STYLE_LOCK}}",
            "{{CELL_SEMANTICS}}",
        ):
            self.assertIn(required, GRID_PROMPT)

    def test_bold_ink_caricature_has_a_face_first_contract(self) -> None:
        for required in (
            "怪形优先，动作后置",
            "至少 12 格使用头像或肩部以上近景",
            "最多 4 格使用紧凑半身或全身",
            "脸部或头部占角色视觉面积的 70–90%",
            "至少 8 格",
            "至少两个明显不对称维度",
            "不超过 4 格",
            "先读成黑白粗墨怪萌漫画",
            "最多 3 组主要身份色水彩色块群",
            "不按连通域机械计数",
            "不按每格像素机械判罚",
            "常规可爱全身宠物贴纸",
        ):
            self.assertIn(required, STYLES)
        for required in (
            "至少 12 格为头像或肩部以上近景",
            "少于 12 格",
            "至少 8 格",
            "两个明显不对称维度",
            "常规对称萌脸超过 4 格",
            "主轮廓线宽",
            "负空间主导",
        ):
            self.assertIn(required, QA)

    def test_run_evidence_is_preserved_for_systematic_audits(self) -> None:
        for required in (
            "generation-prompt.txt",
            "attempt-01-source-sheet.png",
            "attempt-02-source-sheet.png",
            "source-qa.json",
            "不得覆盖失败尝试",
            "selected_attempt",
        ):
            self.assertIn(required, SKILL)

    def test_first_pass_style_preflight_and_tiered_qa(self) -> None:
        for required in (
            "首轮提示词预检",
            "发现冲突就改提示词",
            "首轮抗漂移",
            "outer-silhouette volume",
            "Rendering priority",
        ):
            self.assertIn(required, GRID_PROMPT)
        for required in (
            "照片只提供身份，不提供毛发渲染",
            "2–6 个大而圆润的外轮廓起伏",
            "3–7 个大而有力的外轮廓毛簇",
            "内部短毛线",
        ):
            self.assertIn(required, STYLES)
        for required in (
            "完整标准包源图硬失败",
            "默认非阻断 warning",
            "边缘抗锯齿",
        ):
            self.assertIn(required, QA)

    def test_single_whole_sheet_repair_contract(self) -> None:
        for document in (SKILL, IDENTITY, STYLES, QA):
            self.assertIn("整图修复一次", document)
        self.assertIn("不单格补画", SKILL)
        self.assertIn("只有诊断提取实际失败时", SKILL)
        self.assertIn("优先先调整提取参数重跑", SKILL)
        self.assertIn("透明化失败先重新提取", SKILL)
        self.assertIn("默认阶段先重跑透明提取", QA)
        self.assertIn("第二张仍无法完整切出 16 张就停止", SKILL)
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, QA])
        for removed in ("3 个以上文字错误", "其余情况只修复失败项", "失败格子"):
            self.assertNotIn(removed, core)

    def test_only_current_resources_remain(self) -> None:
        scripts = {path.name for path in (SKILL_DIR / "scripts").glob("*.py")}
        references = {path.name for path in (SKILL_DIR / "references").glob("*.md")}
        tests = {path.name for path in (SKILL_DIR / "tests").glob("test_*.py")}
        self.assertEqual(
            scripts,
            {
                "extract_grid.py",
                "finalize.py",
                "prepare_references.py",
                "style_presets.py",
                "validate.py",
            },
        )
        self.assertEqual(
            references,
            {
                "grid-prompt-template.md",
                "identity-and-style.md",
                "output-contract.md",
                "qa-rubric.md",
                "style-presets.md",
                "wechat-specifications.md",
            },
        )
        self.assertEqual(
            tests,
            {
                "test_delivery.py",
                "test_extract_grid.py",
                "test_prepare_references.py",
                "test_skill_contract.py",
            },
        )
        self.assertFalse((SKILL_DIR / "assets").exists())
        forbidden_artifacts = [
            path
            for path in SKILL_DIR.rglob("*")
            if path.name == ".DS_Store"
            or path.name == "__pycache__"
            or path.suffix == ".pyc"
        ]
        self.assertEqual(forbidden_artifacts, [])

    def test_removed_workflows_do_not_survive_in_core_docs(self) -> None:
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, OUTPUT, QA])
        for removed in (
            "split_grid.py",
            "transparentize.py",
            "IP 母版",
            "无字母版",
            "OPTIONAL REFERENCE B",
            "#00ff00",
            "remove_chroma",
            "deterministic local typesetting",
        ):
            self.assertNotIn(removed, core)

    def test_agent_metadata_matches_entry(self) -> None:
        for required in (
            "$koi-pet-stickers",
            "一张宠物照片和名字",
            "Q萌手绘贴纸",
            "小红书REDSkill",
            "4×4宠物IP表情包大图",
            "16张透明PNG表情",
            "allow_implicit_invocation: true",
        ):
            self.assertIn(required, METADATA)

    def test_visual_and_machine_qa_remain_mandatory(self) -> None:
        for required in (
            "透明单格",
            "RENDERED_TEXT_PLAN",
            "`NONE` 格",
            "相邻格残留",
            "scripts/validate.py",
            "机器通过不等于文字准确或身份正确",
        ):
            self.assertIn(required, QA)
        self.assertIn("qa-report.json", OUTPUT)
        self.assertLess(len(SKILL.splitlines()), 180)

    def test_reference_roles_and_pose_diversity(self) -> None:
        for required in (
            "唯一身份依据",
            "style-compatible invariant",
            "same straight-on contour may appear in no more than four cells",
        ):
            self.assertIn(required, GRID_PROMPT)
        self.assertIn("不得让同一正脸模板重复超过四格", IDENTITY)
        self.assertIn("同一正脸模板不得重复超过四格", QA)
        self.assertIn("风格通过不能抵消身份漂移", QA)
        self.assertIn("Adjacent cells and semantically similar reactions", GRID_PROMPT)
        self.assertIn("语义线索", GRID_PROMPT)
        for required in (
            "OPTIONAL STYLE REFERENCES",
            "only for high-level line weight and rhythm",
            "Never copy or import their characters",
            "sole identity authority",
        ):
            self.assertIn(required, GRID_PROMPT)
        self.assertIn("风格参考图不得贡献角色身份", IDENTITY)

    def test_emotion_is_locked_but_actions_accents_and_text_presence_are_open(self) -> None:
        for required in (
            "无需在 `CELL_SEMANTICS` 中预先声明",
            "情绪装饰可按语义自由添加",
        ):
            self.assertIn(required, STYLES)
        self.assertIn("不按情绪装饰是否与 `CELL_SEMANTICS` 一致判定失败", QA)
        self.assertIn("情绪语义缺失、相反", QA)
        self.assertIn("动作、姿势和装饰的具体形式不作为硬失败", QA)
        self.assertIn("遮住文字后语义仍可理解", IDENTITY)
        self.assertIn("Do not treat expressive symbols as a checklist", GRID_PROMPT)
        self.assertIn("A `NONE` cell must contain no letters", GRID_PROMPT)
        for forbidden_letter_like_text in ("Zzz", "ZZZ", "Hi", "OK", "SOS"):
            self.assertIn(forbidden_letter_like_text, GRID_PROMPT)
        self.assertIn("用户明确指定“全中文、全无字、混合、其他语言或自定义文案”", STYLES)
        self.assertIn("不是动作清单，也不是可见文字清单", GRID_PROMPT)
        core = "\n".join([SKILL, IDENTITY, STYLES, GRID_PROMPT, QA])
        for removed in (
            "只有在对应 `CELL_SEMANTICS` 中明确列出时才允许生成",
            "Every prop and emotion accent must be explicitly named",
            "未规划的标点",
        ):
            self.assertNotIn(removed, core)
        self.assertNotIn("复用同一几何脸模板", STYLES)
        self.assertIn("不能复用完全相同的正脸轮廓", STYLES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
