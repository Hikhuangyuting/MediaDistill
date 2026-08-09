from __future__ import annotations

import re
from typing import Any

from src.core.config import Settings
from src.core.models import KnowledgeDoc
from src.core.paths import WorkspacePaths
from src.core.registry import AssetRegistry
from src.core.utils import ensure_dir, format_timestamp, read_json, write_json
from src.knowledge.schemas import validate_knowledge
from src.vision.value_gate import filter_valuable_vision


def synthesize_from_transcript(settings: Settings, asset_id: str) -> KnowledgeDoc:
    """Audio-first DesignBrain synthesis from transcript (+ optional valuable vision)."""
    registry = AssetRegistry(settings)
    meta = registry.load_meta(asset_id)
    wp = WorkspacePaths(settings, asset_id)
    transcript = read_json(wp.transcript_full)
    text = transcript.get("text") or ""
    segs = transcript.get("segments") or []

    title = meta.source.filename.rsplit(".", 1)[0]
    themes = _extract_themes(text)
    quotes = _pick_quotes(segs, limit=6)
    principles = _principles_from_text(text, themes)
    methods = _methods_from_text(text)
    practices = _practices_from_text(text)
    components = _components_from_text(text)
    systems = _systems_from_text(text)

    valuable_vision = []
    if wp.vision_dir.exists():
        raw = [
            read_json(p) for p in sorted(wp.vision_dir.glob("*.json")) if not p.name.startswith("_")
        ]
        valuable_vision = filter_valuable_vision(raw)

    screenshot_refs = [
        {
            "time": format_timestamp(float(v.get("time_sec") or 0)),
            "frame_id": v.get("frame_id", ""),
            "caption": (v.get("summary") or "")[:120],
        }
        for v in valuable_vision[:8]
    ]

    timeline_refs = [
        {
            "time": format_timestamp(float(q.get("start") or 0)),
            "quote": (q.get("text") or "").strip(),
            "segment_id": q.get("segment_id"),
        }
        for q in quotes
    ]

    core_problem = _core_problem(text, themes)
    approach = _approach(text, themes)
    context = _context(meta.pipeline_type.value, title, themes)
    reflection = _reflection(text, themes)
    reusable = _reusable(text, principles, methods)
    brain = _designbrain_blurb(title, principles, methods, themes)

    source: dict[str, Any] = {
        "type": meta.pipeline_type.value,
        "filename": meta.source.filename,
    }
    dur = meta.source.duration_sec or transcript.get("duration_sec")
    if dur:
        source["duration_sec"] = float(dur)

    doc = KnowledgeDoc(
        asset_id=asset_id,
        source=source,
        topic=title,
        design_context=context,
        core_problem=core_problem,
        design_approach=approach,
        design_principles=principles,
        borrowable_methods=methods,
        components=components,
        design_systems=systems,
        interaction_patterns=practices,
        reusable_experience=reusable,
        my_reflection=reflection,
        designbrain_knowledge=brain,
        tags=_tags(title, themes),
        timeline_refs=timeline_refs,
        screenshot_refs=screenshot_refs,
    )

    errors = validate_knowledge(doc.to_dict(), settings)
    if errors:
        # soften empty arrays if any
        raise ValueError("; ".join(errors))

    ensure_dir(wp.knowledge_dir)
    write_json(wp.knowledge_json, doc.to_dict())
    write_json(
        wp.course_summary,
        {
            "title": doc.topic,
            "core_ideas": [doc.core_problem, doc.design_approach],
            "principles": doc.design_principles,
            "methods": doc.borrowable_methods,
            "practices": doc.interaction_patterns,
            "cases": doc.components,
            "insights": [doc.my_reflection],
            "ai_summary": doc.designbrain_knowledge,
        },
    )
    return doc


def _extract_themes(text: str) -> list[str]:
    catalog = [
        ("AI工具", ["工具", "prompt", "题字词", "上下文", "skill", "scale", "秒悟", "秒误"]),
        ("审美品位", ["品位", "品味", "审美", "风格", "DiMD", "Design"]),
        ("认知能力", ["认知", "焦虑", "判断力", "快乐", "创造"]),
        ("Agentic", ["agent", "Agent", "循环", "目标", "自动化"]),
        ("应用构建", ["应用", "webcoding", "部署", "发布", "小程序"]),
        ("设计新生", ["新生", "观望", "发生", "设计师"]),
        ("近眼交互", ["眼镜", "近眼", "智能眼镜", "五感"]),
    ]
    found = []
    for name, keys in catalog:
        if any(k.lower() in text.lower() for k in keys):
            found.append(name)
    return found or ["设计知识"]


def _pick_quotes(segs: list[dict], limit: int = 6) -> list[dict]:
    scored = []
    keys = ["原则", "品位", "工具", "认知", "AI", "设计", "方法", "重要", "不是", "应该"]
    for s in segs:
        t = (s.get("text") or "").strip()
        if len(t) < 18:
            continue
        score = sum(1 for k in keys if k in t) + min(len(t) / 80, 2)
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    out = []
    seen = set()
    for _, s in scored:
        t = s.get("text", "").strip()
        key = t[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _principles_from_text(text: str, themes: list[str]) -> list[str]:
    rules = []
    if "工具" in text or "AI工具" in themes:
        rules.append("工具学习要抓住能力跃迁，而不是追逐过时的操作细节（学得够晚等于没学）")
    if "品位" in text or "品味" in text or "审美" in text:
        rules.append("品位包含约束与敏感性；仅有风格约束无法替代人对细节的敏感")
    if "认知" in text:
        rules.append("模型决定下限，工程决定边界，个人品位决定上限")
    if "skill" in text.lower() or "scale" in text.lower() or "Skill" in text:
        rules.append("优秀 Skill 的核心句子必须亲手写；通读优秀 Skill 是最好的学习方式")
        rules.append("实践是检验 Skill 的唯一标准；超出自身认知的 Skill 无法真正创造")
    if "应用" in text:
        rules.append("当构建成本趋近于零，产品从昂贵工具变为日常沟通媒介；快乐与价值优先于规模幻想")
    if "焦虑" in text:
        rules.append("把抽象焦虑转成可行动的工具/品位/认知三条提升路径")
    if not rules:
        rules = [
            "从口语分享中提炼可复用原则，而非保留流水账",
            "每条原则应能指导后续设计决策",
            "优先沉淀可迁移方法而非单次案例细节",
        ]
    return rules[:8]


def _methods_from_text(text: str) -> list[str]:
    methods = []
    if "秒悟" in text or "秒误" in text or "瞄悟" in text:
        methods.append("自然语言 → 端到端应用构建 → 云服务/域名/登录一体化发布")
        methods.append("先并行探索多种风格方案，选定后再落地为完整 React 应用（Design 模式）")
    if "skill" in text.lower() or "scale" in text.lower():
        methods.append("用费曼学习法写 Skill：教 AI 即梳理自己的解题思路")
        methods.append("Skill 必须随模型演进迭代，避免把好模型锁死在过时框架里")
    if "品味" in text or "品位" in text or "风格" in text:
        methods.append("品牌调性 = 语言风格 + 字体/资产 + Token/Motion，而非一层浅表主题皮肤")
    if "许愿" in text or "反馈" in text:
        methods.append("用轻量应用收集真实用户愿望/反馈，贴近用户而非只做演示")
    if not methods:
        methods = [
            "章节化转写 → 抽原则 → 写检查清单",
            "用时间戳引用锚定高价值观点",
        ]
    return methods[:8]


def _practices_from_text(text: str) -> list[str]:
    practices = []
    if "应用" in text:
        practices.append("把原本 PPT 能讲清的事克制做成应用；应用应服务真实流程")
    if "token" in text.lower() or "确认" in text:
        practices.append("警惕「不断确认按钮」式空转消耗；创造过程要有可交付结果")
    if "扫码" in text or "分享" in text:
        practices.append("Demo 必须可分享：解决部署/域名/登录最后一公里")
    if not practices:
        practices = ["先验证问题成立，再固化为可复用流程"]
    return practices[:6]


def _components_from_text(text: str) -> list[str]:
    comps = []
    mapping = {
        "秒悟/秒误应用平台": ["秒悟", "秒误", "瞄悟"],
        "风格探索 Agent": ["并行", "风格方案", "agent"],
        "许愿墙": ["许愿"],
        "毛玻璃调参工具": ["锚玻璃", "毛玻璃"],
        "AI 捏脸工具": ["捏脸"],
        "AI BTI 测试": ["BTI", "BTI"],
    }
    for name, keys in mapping.items():
        if any(k in text for k in keys):
            comps.append(name)
    return comps or ["课程观点卡片", "原则清单"]


def _systems_from_text(text: str) -> list[str]:
    systems = []
    if "Token" in text or "Motion" in text or "字体" in text:
        systems.append("品牌设计系统（字体/资产/Token/Motion）")
    if "Skill" in text or "skill" in text.lower() or "scale" in text.lower():
        systems.append("Skill/Agent 工作流规范")
    if not systems:
        systems.append("DesignBrain 条目模板")
    return systems


def _core_problem(text: str, themes: list[str]) -> str:
    if "焦虑" in text and ("工具" in text or "品位" in text):
        return "在 AI 焦虑语境下，设计师如何同时提升工具能力、审美品位与认知，而不是被课程/口号反复收割。"
    if "新生" in text:
        return "当 AI 对设计行业的影响从观望进入真实发生，设计师如何定义新生角色与能力边界。"
    if "眼镜" in text or "近眼" in text:
        return "近眼/智能硬件交互如何从平面 GUI 迁移到更接近人际的多通道体验。"
    return f"围绕「{' / '.join(themes[:3])}」，提炼可复用的设计决策与方法，避免停留在情绪与口号。"


def _approach(text: str, themes: list[str]) -> str:
    if "工具" in text and ("品位" in text or "品味" in text) and "认知" in text:
        return "用「工具—品位—认知」三层框架拆解 AI 时代设计师能力；用端到端产品实践验证观点。"
    return "以完整转写为主证据，抽取可迁移原则与方法，辅以时间戳引用沉淀 DesignBrain 条目。"


def _context(ptype: str, title: str, themes: list[str]) -> str:
    kind = "视频课程/分享" if ptype == "video" else "播客/访谈"
    return f"{kind}《{title}》。主题线索：{', '.join(themes)}。知识提炼以语音内容为主。"


def _reflection(text: str, themes: list[str]) -> str:
    if "敏感性" in text or "约束" in text:
        return "AI 可以把品位编码为约束，但替代不了人对世界的敏感性；风格产品化后要警惕平均化的新平庸。"
    if "快乐" in text:
        return "构建成本下降后，创造过程的快乐与对小群体的真实价值，比宏大商业叙事更重要。"
    return "把分享中的判断写成可检验原则，才能进入长期知识库而不是一次性共鸣。"


def _reusable(text: str, principles: list[str], methods: list[str]) -> str:
    return (
        "可复用组合：" + "；".join(principles[:2]) + "。方法入口：" + "；".join(methods[:2]) + "。"
    )


def _designbrain_blurb(
    title: str, principles: list[str], methods: list[str], themes: list[str]
) -> str:
    return (
        f"《{title}》DesignBrain 摘要。主题={','.join(themes)}。"
        f"原则数={len(principles)}，方法数={len(methods)}。"
        "检索标签见 tags；引用见 timeline_refs。"
    )


def _tags(title: str, themes: list[str]) -> list[str]:
    tags = ["DesignBrain", *themes]
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", title):
        if len(token) >= 2:
            tags.append(token)
            break
    # dedupe preserve order
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out[:12]
