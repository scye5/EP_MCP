"""L3 决策合成层：classify_agn 的核心逻辑。

严格实现主文档 2.2 / 2.3，并在代码中修复 v1.0 的 5 处审查意见：
  1. E9(Compton-thick) 成立 -> 直接 CONFIRMED（遮蔽端特例），SF 一票否决对其豁免；
  2. BPT 分界线写死于 evidence.BPT_BOUNDARIES（见 criteria.compute_bpt）；
  3. 默认线表与波长覆盖校验在 tools.get_spectrum（见 tools.py）；
  4. 每条证据支持 refcode / spectral_ref 溯源，无光谱引用的分类证据不得升强；
  5. catalog_selection_functions 作为入参落地，选择函数随结果强制声明。

零外部依赖，纯函数。
"""

from __future__ import annotations

from typing import Any

from .criteria import compute_bpt
from .evidence import BAND_OF, EVIDENCE, STRONG_IDS, score_of

VALID_IDS = frozenset(EVIDENCE)


def classify_agn(
    object_id: str,
    evidence: list[dict[str, Any]],
    strategy: str = "purity",
    catalog_selection_functions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """汇总多波段证据，输出最终标签、置信度与选择函数声明。

    参数
    ----
    evidence: 每项 ``{"id": "E2", "value": {...}, "source": "...",
                       "refcode": "...", "spectral_ref": true}``。
              ``refcode`` / ``spectral_ref`` 为可选溯源字段（审查意见 4）。
    strategy: ``purity``（严格溯源 + SF 一票否决）或 ``completeness``（宽松溯源，
              SF 不否决而降为待证）。
    catalog_selection_functions: 星表流量限/覆盖/红移范围（审查意见 5）。
    """
    if strategy not in ("purity", "completeness"):
        raise ValueError("strategy 只能是 'purity' 或 'completeness'")

    trace: list[str] = [f"输入 {len(evidence)} 条证据，策略={strategy}"]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    # ---- 步骤 1：逐条校验有效性、正向性与溯源 ----
    normalized: list[dict[str, Any]] = []
    for item in evidence:
        eid = str(item.get("id", ""))
        if eid not in VALID_IDS:
            rejected.append({"id": eid, "reason": "未知证据 ID"})
            trace.append(f"拒绝 {eid}: 未知 ID")
            continue
        value = item.get("value") or {}
        if not _is_positive(eid, value):
            rejected.append({"id": eid, "reason": "判据未成立（值为阴性/不足）"})
            trace.append(f"拒绝 {eid}: 判据未成立")
            continue
        norm = dict(item)
        norm["value"] = value
        norm["refcode"] = item.get("refcode")
        norm["spectral_ref"] = item.get("spectral_ref")
        normalized.append(norm)

    # ---- 步骤 2：溯源过滤（审查意见 4）----
    # 文献分类映射来的光学强证据（E1/E2），若无光谱引用则不得计强。
    sourced: list[dict[str, Any]] = []
    for n in normalized:
        from_classification = "classification" in str(n.get("source", "")).lower()
        if (
            n["id"] in ("E1", "E2")
            and from_classification
            and n["spectral_ref"] is not True
        ):
            if strategy == "purity":
                rejected.append({"id": n["id"], "reason": "文献分类无光谱引用，不得升强证据"})
                trace.append(f"拒绝 {n['id']}: 分类来源且 spectral_ref!=True（纯度策略）")
                continue
            else:
                n["downgraded"] = True
                trace.append(f"降级 {n['id']}: 分类无光谱引用，完备策略仅记辅助分")
        sourced.append(n)

    # ---- 步骤 3：独立性约束——同波段只计最高分一条 ----
    by_band: dict[str, list[dict[str, Any]]] = {}
    for n in sourced:
        band = BAND_OF[n["id"]]
        by_band.setdefault(band, []).append(n)

    for band, group in by_band.items():
        def rank(n: dict[str, Any]) -> tuple[int, int, int]:
            base = 1 if n.get("downgraded") else score_of(n["id"])
            # 有 refcode、有光谱引用者优先保留
            return (base, 1 if n.get("refcode") else 0, 1 if n.get("spectral_ref") is True else 0)

        group.sort(key=rank, reverse=True)
        winner = group[0]
        accepted.append(winner)
        for loser in group[1:]:
            # E4(WHAN) 是 LINER 简并的专用追加判据，与 E2(BPT) 同源但用途不同，
            # 允许共存（不计叠加分），否则 LINER 规则永远无法满足。
            if loser["id"] == "E4" and winner["id"] == "E2":
                loser["non_additive"] = True
                accepted.append(loser)
                trace.append(f"保留 {loser['id']}: WHAN 为 LINER 追加判据，与 E2 共存但不叠加分")
                continue
            rejected.append({
                "id": loser["id"],
                "reason": f"与 {winner['id']} 同属 {band} 波段，独立性约束只计最高分一次",
            })
            trace.append(f"拒绝 {loser['id']}: 与 {winner['id']} 同波段({band})，不叠加")

    # 计分：非叠加证据(WHAN追加)不计分；BPT 落 SF/LINER/COMPOSITE 的 E2
    # 是有效测量但不构成 AGN 正向证据，同样不计强分（否决/追加规则仍消费它）。
    def contributes(n: dict[str, Any]) -> bool:
        if n.get("non_additive"):
            return False
        if n["id"] == "E2":
            info = _bpt_region(n)
            return bool(info and info.get("region") == "AGN")
        return True

    accepted_ids = {a["id"] for a in accepted}
    strong_ids = {
        a["id"] for a in accepted
        if a["id"] in STRONG_IDS and not a.get("downgraded") and contributes(a)
    }
    score = sum(0 if not contributes(a) else (1 if a.get("downgraded") else score_of(a["id"]))
                for a in accepted)

    # E9 的 value 用于遮蔽端判定
    e9_item = next((a for a in accepted if a["id"] == "E9"), None)
    bpt_item = next((a for a in accepted if a["id"] == "E2"), None)
    bpt_info = _bpt_region(bpt_item) if bpt_item else None
    region = bpt_info.get("region") if bpt_info else None
    sf_stable = region == "SF" and not bpt_info.get("region_unstable", False)
    liner = region in ("LINER", "COMPOSITE")
    other_band_support = any(BAND_OF[a["id"]] != "optical" for a in accepted)

    caveats: list[str] = []
    if not catalog_selection_functions:
        caveats.append("未提供星表选择函数，本结果不可用于人口统计或占比推断")

    # ---- 步骤 4：E9 遮蔽端特例（审查意见 1、5）----
    # E9 成立即 CONFIRMED，即使光学为 Type 2 / BPT 落 SF——SF 否决对其豁免。
    if e9_item is not None:
        label = "CONFIRMED_AGN"
        confidence = _confidence(label, score, len(strong_ids))
        trace.append("E9(Compton-thick) 成立 -> 遮蔽端特例直接 CONFIRMED，SF 否决豁免")
        caveats.append("Compton-thick 由硬 X 直接确认；光学光谱可能仅显示宿主恒星形成")
        return _assemble(object_id, label, confidence, score, accepted, rejected,
                         strategy, catalog_selection_functions, caveats,
                         " -> ".join(trace), band_info(by_band))

    # ---- 步骤 5：BPT SF 一票否决（审查意见 5：purity 执行，completeness 不执行）----
    if sf_stable and not other_band_support:
        if strategy == "purity":
            label = "LIKELY_NON_AGN"
            confidence = _confidence(label, score, len(strong_ids))
            trace.append("BPT 稳定 SF 区且无独立波段支持 -> 一票否决 LIKELY_NON_AGN（不进入计分）")
            caveats.append("仅凭光学 SF 区否决；遮蔽端缺硬 X 时可能漏 Compton-thick")
            return _assemble(object_id, label, confidence, score, accepted, rejected,
                             strategy, catalog_selection_functions, caveats,
                             " -> ".join(trace), band_info(by_band))
        else:
            trace.append("BPT SF 区，但完备策略保留为待证而非否决")
            caveats.append("完备策略下 SF 区未被否决，请补硬 X 排除遮蔽端")

    # ---- 步骤 6：LINER 简并规则 ----
    has_whan = "E4" in accepted_ids
    has_xray = bool({"E7", "E8", "E9"} & accepted_ids)
    if liner:
        if not (has_whan or has_xray):
            label = "INDETERMINATE"
            confidence = _confidence(label, score, len(strong_ids))
            trace.append("LINER/composite 区无 WHAN 或 X 射线追加 -> 禁止单独定性 INDETERMINATE")
            caveats.append("LINER 可能是低光度 AGN 或老年恒星族，需 WHAN(E4)/X 射线(E7/E9)")
            return _assemble(object_id, label, confidence, score, accepted, rejected,
                             strategy, catalog_selection_functions, caveats,
                             " -> ".join(trace), band_info(by_band))
        trace.append("LINER/composite 区有 WHAN 或 X 射线追加，允许继续合成")

    # ---- 步骤 7：时域暂现待证 ----
    # 只有"光变触发 + 除光变外无任何 AGN 证据"才是暂现待证；
    # E5(WISE 颜色) 等辅助证据虽不计强分，但已是 AGN 线索，
    # 此时 E5+E11 应走 2.2 的 CANDIDATE 条件而非被暂现规则拦截。
    has_variability = "E11" in accepted_ids or "E12" in accepted_ids
    other_agn_evidence = accepted_ids - {"E11", "E12"}
    if has_variability and not other_agn_evidence:
        label = "TRANSIENT_CANDIDATE"
        confidence = _confidence(label, score, len(strong_ids))
        trace.append("光变触发但光谱未归类 -> TRANSIENT_CANDIDATE（需区分 CL/TDE/SN/耀星）")
        caveats.append("WXT 1.3' 定位假阳性高，须 FXT 跟进与 Gaia 剔除耀星")
        return _assemble(object_id, label, confidence, score, accepted, rejected,
                         strategy, catalog_selection_functions, caveats,
                         " -> ".join(trace), band_info(by_band))

    # ---- 步骤 8：标签准入（2.2）----
    strong_only_combo = accepted_ids == {"E5", "E11"}
    liner_with_support = liner and (has_whan or has_xray) if liner else False

    if (len(strong_ids) >= 2) or (len(strong_ids) >= 1 and score >= 3):
        label = "CONFIRMED_AGN"
        trace.append(f"强证据 {len(strong_ids)} 条、总分 {score} -> CONFIRMED_AGN")
    elif score == 2 or strong_only_combo or liner_with_support:
        label = "CANDIDATE_AGN"
        trace.append(f"总分 {score} / 仅 E5+E11 / LINER+支持 -> CANDIDATE_AGN")
    else:
        label = "INDETERMINATE"
        trace.append(f"总分 {score}、强证据 {len(strong_ids)} -> 证据不足 INDETERMINATE")

    confidence = _confidence(label, score, len(strong_ids))
    if label == "CONFIRMED_AGN":
        caveats.append("确认依赖现有证据覆盖；未覆盖波段（如射电/硬 X）仍可能存在选择效应")
    return _assemble(object_id, label, confidence, score, accepted, rejected,
                     strategy, catalog_selection_functions, caveats,
                     " -> ".join(trace), band_info(by_band))


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _is_positive(eid: str, value: Any) -> bool:
    """判据是否成立。兼容各工具的 output 结构与直接布尔值。

    value 为空一律视为"提交即成立"（调用方已预筛），并在 caveats 中不做保证。
    """
    if value is None or value == {} or value is True:
        return True
    if not isinstance(value, dict):
        return bool(value)

    # 统一的正向标志
    for key in ("is_candidate", "is_agn", "is_compton_thick", "is_obscured", "is_variable",
                "detected", "broad_component", "significant"):
        if key in value and value[key] is False:
            return False

    if eid == "E1":
        fwhm = value.get("fwhm_kms") or value.get("fwhm")
        if fwhm is not None:
            return float(fwhm) > 1000
        return bool(value.get("is_candidate") or value.get("broad_component") or
                    value.get("line_type") in ("BEL", "broad"))
    if eid == "E2":
        region = value.get("region")
        if region:
            # SF/LINER/COMPOSITE/AGN 都是有效 BPT 测量结果；是否为正向证据
            # 由 contributes() 在计分阶段判断（否决/LINER 规则需要消费它们）。
            return region in ("AGN", "SF", "LINER", "COMPOSITE")
        return bool(value.get("evidence_id") == "E2" or
                    ("log_nii_ha" in value and "log_oiii_hb" in value))
    if eid == "E3":
        return bool(value.get("detected", True))
    if eid == "E5":
        if "is_candidate" in value:
            return bool(value["is_candidate"])
        color = value.get("w1_minus_w2")
        return color is not None and float(color) >= 0.8
    if eid == "E7":
        lx = value.get("lx_2_10") or value.get("lx")
        if lx is not None:
            return float(lx) > 1e42
        return bool(value.get("is_agn", True))
    if eid == "E8":
        nh = value.get("nh")
        if nh is not None:
            return float(nh) > 1e22
        return bool(value.get("is_obscured", True))
    if eid == "E9":
        nh = value.get("nh")
        ew = value.get("fe_kalpha_ew")
        if nh is not None and float(nh) > 1.5e24:
            return True
        if ew is not None and float(ew) > 1.0:
            return True
        return bool(value.get("is_compton_thick", False))
    if eid == "E11":
        return bool(value.get("is_variable", True))
    if eid == "E12":
        return bool(value.get("mechanism") in ("luminosity", "obscuration") or
                    value.get("nh_changed") is not None)
    # E4/E6/E10：提交即视为正向（诊断类证据）
    return True


def _bpt_region(item: dict[str, Any]) -> dict[str, Any] | None:
    value = item.get("value") or {}
    if value.get("region"):
        return value
    if "log_nii_ha" in value and "log_oiii_hb" in value:
        return compute_bpt(value["log_nii_ha"], value["log_oiii_hb"],
                           ew_ha=value.get("ew_ha"))
    return None


def _confidence(label: str, score: int, n_strong: int) -> float:
    if label == "CONFIRMED_AGN":
        return round(min(0.99, 0.90 + 0.02 * max(score - 3, 0)), 2)
    if label == "CANDIDATE_AGN":
        return round(min(0.85, 0.55 + 0.05 * score), 2)
    if label == "LIKELY_NON_AGN":
        return 0.85
    if label == "TRANSIENT_CANDIDATE":
        return 0.45
    return round(min(0.45, 0.25 + 0.05 * (score + n_strong)), 2)


def band_info(by_band: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"band": band, "accepted": [n["id"] for n in group]} for band, group in by_band.items()]


def _assemble(
    object_id: str,
    label: str,
    confidence: float,
    score: int,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    strategy: str,
    catalog_selection_functions: list[dict[str, Any]] | None,
    caveats: list[str],
    decision_trace: str,
    bands: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted_out = [
        {"id": a["id"], "band": BAND_OF[a["id"]], "score": 1 if a.get("downgraded") else score_of(a["id"]),
         "source": a.get("source"), "refcode": a.get("refcode"),
         "spectral_ref": a.get("spectral_ref"), "value": a.get("value")}
        for a in accepted
    ]
    # 选择函数：汇总输入，标注限制星表（审查意见 5）
    sf_summary: dict[str, Any] = {"wavebands": sorted({b["band"] for b in bands}), "provided": bool(catalog_selection_functions)}
    if catalog_selection_functions:
        sf_summary["catalogs"] = catalog_selection_functions
        limiting = min(catalog_selection_functions,
                       key=lambda c: _flux_limit_number(c.get("flux_limit")))
        sf_summary["limiting_catalog"] = limiting.get("catalog")
    else:
        sf_summary["flux_limits"] = None
        sf_summary["sky_coverage"] = None
        sf_summary["z_range"] = None
    return {
        "object_id": object_id,
        "label": label,
        "confidence": confidence,
        "score": score,
        "strategy": strategy,
        "evidence_accepted": accepted_out,
        "evidence_rejected": rejected,
        "selection_function": sf_summary,
        "caveats": caveats,
        "decision_trace": decision_trace,
    }


def _flux_limit_number(limit: Any) -> float:
    if limit is None:
        return float("-inf")
    if isinstance(limit, (int, float)):
        return float(limit)
    import re
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(limit))
    return float(m.group()) if m else float("-inf")
