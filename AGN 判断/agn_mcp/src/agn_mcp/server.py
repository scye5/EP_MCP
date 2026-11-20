"""AGN 判定 MCP 服务：FastMCP 注册层。

把 tools.py 的 14 个函数注册为 MCP tools，并暴露 5 个 resources 与 4 个 prompts
（对齐接口设计 v1.0 第 4.2 / 4.4 / 4.5 节）。

启动（需先 pip install mcp）：
    python -m agn_mcp.server              # stdio（默认，供 Agent 连接）
    python -m agn_mcp.server --transport sse --port 8000
    NED_OFFLINE=1 python -m agn_mcp.server   # 离线自测

未安装 mcp 时，本模块仍可 import，tools 函数可直接调用；只有 create_app() 会提示安装。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import tools
from .evidence import BPT_BOUNDARIES, EVIDENCE

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_MCP = True
except ImportError:  # pragma: no cover - 环境未装 mcp 时的优雅降级
    FastMCP = None  # type: ignore[assignment]
    _HAS_MCP = False


# ---------------------------------------------------------------------------
# Resources 内容（只读知识资源）
# ---------------------------------------------------------------------------
def _evidence_table_resource() -> str:
    return json.dumps(
        {
            eid: {
                "band": e.band, "criterion": e.criterion, "threshold": e.threshold,
                "strength": e.strength, "score": e.score,
                "reliability": e.reliability, "completeness": e.completeness,
                "limitation": e.limitation, "reference": e.reference,
            }
            for eid, e in EVIDENCE.items()
        },
        ensure_ascii=False, indent=2,
    )


def _decision_rules_resource() -> str:
    return json.dumps(
        {
            "scoring": "strong=2 (E1,E2,E3,E6,E7,E9,E10,E12); auxiliary=1 (E4,E5,E8,E11)",
            "one_veto": "BPT stable SF + no independent band -> LIKELY_NON_AGN (no scoring)",
            "liner_rule": "LINER/composite cannot be classified alone; need WHAN(E4) or X-ray(E7/E9)",
            "obscured_exception": "E9 (Compton-thick) -> CONFIRMED even if optical Type2/SF; SF veto exempt",
            "independence": "same-band multiple criteria count only the single highest score",
            "label_admission": {
                "CONFIRMED_AGN": ">=1 strong & score>=3, OR >=2 strong; no strong counter-evidence",
                "CANDIDATE_AGN": "score==2, OR only E5+E11, OR LINER+independent support",
                "LIKELY_NON_AGN": "BPT stable SF & no independent band support",
                "TRANSIENT_CANDIDATE": "variability trigger but spectrum unclassified",
                "INDETERMINATE": "insufficient SNR or missing band coverage",
            },
            "bpt_boundaries": BPT_BOUNDARIES,
            "selection_function": "mandatory; no population statistics without it",
        },
        ensure_ascii=False, indent=2,
    )


REFERENCES_CORE = """核心文献（Hickox & Alexander 2018 方法论 + 判据出处）
- Hickox & Alexander 2018, ARA&A 56, 625 (arXiv:1806.04680): reliability/completeness 不相关；
  §2.5 单一波段无法完备且可靠地选 AGN；p.23 CT 内禀 27±4% vs BAT 观测 8%。
- Netzer 2015, ARA&A 53, 365: 宽 Balmer 线 Type1 判据。
- Kewley 2001 / Kauffmann 2003 / Schawinski 2007: BPT 三条分界。
- Cid Fernandes 2011: WHAN 图解 LINER 简并。
- Stern 2012: WISE W1-W2>=0.8, W2<15.5, reliability 95% / completeness 78%。
- Ulrich 1997: AGN 光变经典综述。
- Fanaroff & Riley 1974: 射电形态。
- EP 团队 WXT 标定 arXiv:2606.28101；EP J062132.0+623837 changing-look arXiv:2610.30959（预印本）。
- 注意：H&A 2018 早于 EP 发射（2024-01），判据引经典、仪器能力引 EP 新文献，不可混成一条引用。"""

CATALOGS_INVENTORY = """星表清单与选择函数（详见 tools.CATALOG_SELECTION_FUNCTIONS）
Milliquas v8 ~102万条，文献汇编非均匀，不可计数统计；SDSS_QSO 均匀 i~19.1；
WISEAGN W2<15.5 完备78%；3XMM 斑点覆盖；eRASS 全天均匀；Swift_BAT 14-195keV；
FIRST 1mJy / NVSS 2.5mJy 射电亮端。选择函数由 query_catalog 随结果强制返回。"""

INSTRUMENTS_EP = """EP 仪器参数
WXT: 0.5-4 keV, R90~1.3', 系统误差0.61', 2024-08~2025-11 全天源表约4370点源/16万次探测；
FXT: 定位~10'', 首批数据 2025-12-11 公开（约200GB, HEASoft 兼容, ep.bao.ac.cn）；
定位：WXT 假阳性高，必须 FXT 跟进才能安全匹配光学/红外对应体。"""


PROMPTS: dict[str, tuple[str, str]] = {
    "sop_single_object": (
        "S1 单源判定 SOP（A1→A9）",
        "对目标 {target} 依次执行：1) resolve_object 取坐标/红移/分类；"
        "2) query_catalog(Milliquas/SDSS_QSO) 查已有光谱证认；"
        "3) get_photometry + wise_agn_selection 得 E5；"
        "4) query_catalog(Swift_BAT/3XMM) + xray_agn_selection 得 E7/E8/E9；"
        "5) get_spectrum + compute_bpt 得 E1/E2/E4；"
        "6) get_lightcurve + analyze_variability 得 E11；"
        "7) classify_agn 合成。注意：NED 分类无光谱引用不得升强证据；"
        "硬 X 缺失须在 caveats 声明遮蔽端不完备；不得据静态分类断言本次增亮是 AGN 耀发。",
    ),
    "sop_batch_search": (
        "S2 批量候选筛选 SOP（B1→B7）",
        "在 {region} 内：crossmatch 多星表（光学1-3'', WISE>=3'', FXT 10'', WXT 1.3'）→ "
        "validate 剔除假匹配 → wise/xray 初筛（保纯度取交集、保完备取并集）→ "
        "find_agn_candidates 命中合成。B6 选择函数不可跳过；"
        "清单完备性由最弱星表决定，不可作人口统计无偏样本。",
    ),
    "sop_time_domain": (
        "S3 时域发现 SOP（C1→C6）",
        "get_lightcurve(EP_WXT) 触发 → crossmatch + Gaia 剔除耀星 → "
        "submit_too/plan_followup 安排 FXT ToO 收紧定位到10'' → "
        "xray_agn_selection + compute_bpt 判 N_H 是否变化（E12）："
        "N_H 未变=吸积盘光度变化，N_H 变=遮蔽变化 → classify_agn 区分 changing-look/TDE/SN。"
        "判据引经典文献，仪器能力引 EP 最新标定，两者分开引用。",
    ),
    "sop_followup": (
        "后随提案论证生成",
        "基于 {candidate_id} 的 current_evidence 与 science_goal 调用 plan_followup，"
        "按信息增益排序观测链；生成提案论证时引用判据文献与选择函数限制，"
        "说明该观测将补上哪条缺失证据（E-ID）及其 reliability/completeness。",
    ),
}


# ---------------------------------------------------------------------------
# 工具 -> MCP 注册元数据（名称、描述、参数 schema 与函数）
# ---------------------------------------------------------------------------
def tool_specs() -> list[dict[str, Any]]:
    """返回 14 个工具的注册规格（与接口设计 4.3 对齐），供 MCP 与文档共用。"""
    return [
        {"name": "resolve_object", "fn": tools.resolve_object,
         "description": "名字/坐标 → J2000 坐标、红移、SIMBAD/NED 已知分类；标注分类是否带光谱引用。",
         "schema": {"type": "object", "properties": {
             "identifier": {"type": "string"}, "resolve_radius_arcsec": {"type": "number", "default": 5}},
             "required": ["identifier"]}},
        {"name": "query_catalog", "fn": tools.query_catalog,
         "description": "按坐标查指定星表，命中源及选择函数随结果返回。",
         "schema": {"type": "object", "properties": {
             "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
             "radius_arcsec": {"type": "number", "default": 3}, "catalog": {"type": "string"},
             "type_filter": {"type": "array", "items": {"type": "string"}}},
             "required": ["ra_deg", "dec_deg", "catalog"]}},
        {"name": "get_photometry", "fn": tools.get_photometry,
         "description": "取多波段测光；非探测返回上限而非插补值。",
         "schema": {"type": "object", "properties": {
             "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
             "bands": {"type": "array", "items": {"type": "string"}}, "target": {"type": "string"}},
             "required": ["ra_deg", "dec_deg"]}},
        {"name": "get_spectrum", "fn": tools.get_spectrum,
         "description": "取光谱与发射线 flux/EW；校验波长覆盖并返回 unobservable_lines。",
         "schema": {"type": "object", "properties": {
             "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
             "survey": {"type": "string", "default": "LAMOST"},
             "lines": {"type": "array", "items": {"type": "string"}}, "target": {"type": "string"}},
             "required": ["ra_deg", "dec_deg"]}},
        {"name": "get_lightcurve", "fn": tools.get_lightcurve,
         "description": "取多巡天光变曲线（EP-WXT/FXT、ZTF、eRASS、Swift_BAT）。",
         "schema": {"type": "object", "properties": {
             "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
             "survey": {"type": "string"}, "band": {"type": "string"},
             "start_mjd": {"type": "number"}, "end_mjd": {"type": "number"}},
             "required": ["ra_deg", "dec_deg", "survey"]}},
        {"name": "crossmatch", "fn": tools.crossmatch,
         "description": "天球坐标交叉匹配，输出角距、命中标记与假匹配校验提示。",
         "schema": {"type": "object", "properties": {
             "left": {"type": "array", "items": {"type": "object"}},
             "right_catalog": {"type": "string"}, "max_error_arcsec": {"type": "number", "default": 3},
             "join": {"type": "string", "default": "1_and_2"}, "validate": {"type": "boolean", "default": True}},
             "required": ["left", "right_catalog"]}},
        {"name": "compute_bpt", "fn": tools.bpt_tool,
         "description": "BPT 线比分区 + WHAN；LINER 区强制追加判据提示。",
         "schema": {"type": "object", "properties": {
             "log_nii_ha": {"type": "number"}, "log_oiii_hb": {"type": "number"},
             "ew_ha": {"type": "number"}, "errors": {"type": "object"},
             "diagram": {"type": "string", "default": "NII"}},
             "required": ["log_nii_ha", "log_oiii_hb"]}},
        {"name": "wise_agn_selection", "fn": tools.wise_tool,
         "description": "WISE 中红外颜色选源；遮蔽不可分辨提示。",
         "schema": {"type": "object", "properties": {
             "w1": {"type": "number"}, "w2": {"type": "number"}, "w2_snr": {"type": "number"},
             "w3": {"type": "number"}, "criteria": {"type": "string", "default": "Stern2012"}},
             "required": ["w1", "w2", "w2_snr"]}},
        {"name": "xray_agn_selection", "fn": tools.xray_tool,
         "description": "X 射线选源与遮蔽/Compton-thick 分类。",
         "schema": {"type": "object", "properties": {
             "band": {"type": "string", "default": "soft_0.5_10"}, "lx_2_10": {"type": "number"},
             "nh": {"type": "number"}, "hardness_ratio": {"type": "number"},
             "fe_kalpha_ew": {"type": "number"}}, "required": ["band"]}},
        {"name": "analyze_variability", "fn": tools.variability_tool,
         "description": "光变显著性/幅度/时标/多波段相关；瞬变污染提示。",
         "schema": {"type": "object", "properties": {
             "lightcurve": {}, "test_periodic": {"type": "boolean", "default": True}},
             "required": ["lightcurve"]}},
        {"name": "classify_agn", "fn": tools.classify_tool,
         "description": "核心：证据合成，输出标签/置信度/证据清单/选择函数声明；禁止单一波段确认。",
         "schema": {"type": "object", "properties": {
             "object_id": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "object"}},
             "strategy": {"type": "string", "enum": ["purity", "completeness"], "default": "purity"},
             "catalog_selection_functions": {"type": "array", "items": {"type": "object"}}},
             "required": ["object_id", "evidence"]}},
        {"name": "find_agn_candidates", "fn": tools.find_agn_candidates,
         "description": "批量候选筛选，带命中标记、置信度与选择函数声明。",
         "schema": {"type": "object", "properties": {
             "region": {"type": "object"}, "catalogs": {"type": "array", "items": {"type": "string"}},
             "criteria": {"type": "array", "items": {"type": "string"}},
             "min_hits": {"type": "number", "default": 2},
             "strategy": {"type": "string", "default": "purity"}},
             "required": ["region", "catalogs"]}},
        {"name": "submit_too", "fn": tools.submit_too,
         "description": "提交 ToO 请求；默认人工确认闸门，返回 pending，不自动对外提交。",
         "schema": {"type": "object", "properties": {
             "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
             "trigger_reason": {"type": "string"}, "instrument": {"type": "string"},
             "urgency": {"type": "string", "default": "medium"}, "justification": {"type": "string"},
             "require_human_confirm": {"type": "boolean", "default": True}},
             "required": ["ra_deg", "dec_deg", "trigger_reason", "instrument"]}},
        {"name": "plan_followup", "fn": tools.plan_followup,
         "description": "按证据缺口规划后随观测链，按信息增益排序。",
         "schema": {"type": "object", "properties": {
             "candidate_id": {"type": "string"}, "current_evidence": {"type": "array", "items": {"type": "string"}},
             "science_goal": {"type": "string"},
             "available_facilities": {"type": "array", "items": {"type": "string"}}},
             "required": ["candidate_id", "science_goal"]}},
    ]


def create_app() -> Any:
    """创建并注册好的 FastMCP 实例。"""
    if not _HAS_MCP:
        raise RuntimeError("未安装 mcp。请运行：pip install mcp  后重试。tools 函数仍可直接 import 使用。")
    mcp = FastMCP("agn-judgment")

    for spec in tool_specs():
        # 用闭包捕获 fn，避免循环变量晚绑定
        fn = spec["fn"]

        def make_tool(tool_fn: Any) -> Any:
            def wrapper(**kwargs: Any) -> dict[str, Any]:
                try:
                    return {"ok": True, "result": tool_fn(**kwargs)}
                except Exception as exc:  # noqa: BLE001
                    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            wrapper.__name__ = tool_fn.__name__
            wrapper.__doc__ = fn.__doc__
            return wrapper

        mcp.tool(name=spec["name"], description=spec["description"])(make_tool(fn))

    # Resources
    mcp.resource("agn://criteria/evidence_table")(lambda: _evidence_table_resource())
    mcp.resource("agn://criteria/decision_rules")(lambda: _decision_rules_resource())
    mcp.resource("agn://references/core")(lambda: REFERENCES_CORE)
    mcp.resource("agn://catalogs/inventory")(lambda: CATALOGS_INVENTORY)
    mcp.resource("agn://instruments/ep")(lambda: INSTRUMENTS_EP)

    # Prompts
    for name, (title, body) in PROMPTS.items():
        mcp.prompt(name=name, description=title)(lambda b=body: b)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="AGN 判定 MCP 服务")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = create_app()
    if args.transport == "sse":
        app.run(transport="sse", port=args.port)
    else:
        app.run(transport="stdio")


if __name__ == "__main__":
    main()
