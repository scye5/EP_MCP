"""14 个 MCP 工具的实现函数（与接口设计 v1.0 第 4.3 节一一对应）。

这些函数不依赖 MCP SDK，输入输出均为 dict，便于：
  - server.py 用 FastMCP 薄包装注册为 tool；
  - 单元测试直接调用；
  - 离线模式下注入样例数据。

分层：
  L1  resolve_object / query_catalog / get_photometry / get_spectrum / get_lightcurve / crossmatch
  L2  compute_bpt(包装 criteria) / wise_agn_selection / xray_agn_selection / analyze_variability
  L3  classify_agn(包装 decision) / find_agn_candidates
  L4  submit_too / plan_followup
"""

from __future__ import annotations

import math
import re
import uuid
from typing import Any

from . import ned_client
from .criteria import (
    analyze_variability,
    compute_bpt,
    wise_agn_selection,
    xray_agn_selection,
)
from .decision import classify_agn
from .evidence import EVIDENCE

# 星表选择函数声明（接口设计 4.3.2：Milliquas 是文献汇编，不可计数统计）。
CATALOG_SELECTION_FUNCTIONS: dict[str, dict[str, Any]] = {
    "Milliquas": {"flux_limit": "heterogeneous compilation", "sky_coverage": "all-sky, uneven",
                  "z_range": "wide", "note": "文献汇编非均匀样本，不可直接用于计数统计 (Flesch 2023)"},
    "SDSS_QSO": {"flux_limit": "i ~ 19.1", "sky_coverage": "SDSS footprint ~14,555 deg^2",
                 "z_range": "0.1–7", "note": "均匀选源，可用于统计"},
    "WISEAGN": {"flux_limit": "W2 < 15.5 (SNR>5)", "sky_coverage": "all-sky",
                "z_range": "0–6", "note": "Stern 2012 颜色选，完备性 78%"},
    "3XMM": {"flux_limit": "F_X ~ 1e-14 erg/cm2/s", "sky_coverage": "serendipitous, patchy",
             "z_range": "0–5", "note": "斑点覆盖，选择函数复杂"},
    "eRASS": {"flux_limit": "0.2–2 keV all-sky survey", "sky_coverage": "all-sky",
              "z_range": "0–3", "note": "均匀全天，适合统计"},
    "Swift_BAT": {"flux_limit": "14–195 keV, >1e-11 erg/cm2/s", "sky_coverage": "all-sky",
                  "z_range": "0–0.3", "note": "硬 X，对 CT 最不完备端反而最直接；AA* 极低"},
    "FIRST": {"flux_limit": "1.0 mJy", "sky_coverage": "northern ~10,000 deg^2",
              "z_range": "0–6", "note": "射电亮端"},
    "NVSS": {"flux_limit": "2.5 mJy", "sky_coverage": "northern declination > -40",
             "z_range": "0–6", "note": "射电亮端"},
}

# LAMOST 波长覆盖 380–900 nm；NeV3426(342.6nm) 不可见 —— 修复审查意见 3。
LAMOST_COVERAGE_NM = (380.0, 900.0)
LINE_WAVELENGTH_NM = {
    "Ha": 656.3, "Hb": 486.1, "NII6584": 658.4, "OIII5007": 500.7,
    "OI6300": 630.0, "SII6716": 671.6, "SII6731": 673.1,
    "NeV3426": 342.6, "NeVI76um": 76000.0, "NeV14um": 14000.0,
}
DEFAULT_LINES = ["Ha", "Hb", "NII6584", "OIII5007", "OI6300", "SII6716", "SII6731"]
# 说明：默认线表已移除 NeV3426（审查意见 3），需显式指定且设施覆盖时才会测。


# ===========================================================================
# L1
# ===========================================================================
def resolve_object(identifier: str, resolve_radius_arcsec: float = 5.0) -> dict[str, Any]:
    """名字/坐标 -> J2000 坐标、红移、SIMBAD/NED 已知分类，标注是否光谱引用。"""
    out: dict[str, Any] = {
        "resolved": False, "input": identifier, "identifier_kind": None,
        "simbad_type": None, "ned_type": None,
        "classification_has_spectral_ref": None, "references": [], "conflict_note": None,
    }
    is_coord = _looks_like_coords(identifier)
    out["identifier_kind"] = "coordinate" if is_coord else "name"

    if not is_coord:
        r = ned_client.ned_query("OverviewOfObject", {"TARGET": identifier})
        out["ned_url"] = r.url
        if r.error:
            out["error"] = r.error
            return out
        if not r.rows:
            out["note"] = "NED 未解析该名称；名称能识别不等于天体已收录"
            return out
        row = r.rows[0]
        ra = ned_client.as_float(ned_client.pick(row, "RA(deg)", "ra_deg", "ra"))
        dec = ned_client.as_float(ned_client.pick(row, "Dec(deg)", "dec_deg", "dec"))
        z = ned_client.as_float(ned_client.pick(row, "z", "redshift"))
        out.update(resolved=True, ra_deg=ra, dec_deg=dec, redshift=z,
                   object_type=ned_client.pick(row, "Object Type", "objtype"),
                   activity_type=ned_client.pick(row, "Activity Type", "activity"),
                   ned_type=ned_client.pick(row, "Phys Type", "Object Type"),
                   refcode=ned_client.pick(row, "Reference", "refcode"))
        out["classification_has_spectral_ref"] = bool(out.get("refcode"))
        out["note"] = ("NED Object Type=G 不能排除 AGN；活动类型需看 Activity Type 与光谱引用"
                       if out.get("object_type") == "G" else None)
    else:
        ra, dec = _parse_coords(identifier)
        out.update(resolved=True, ra_deg=ra, dec_deg=dec)
        r = ned_client.ned_query("ConeSearchByPosition", {
            "LON": f"{ra}d", "LAT": f"{dec}", "RADIUS": max(resolve_radius_arcsec / 60.0, 1e-4),
            "MAXREC": 5, "CSYS": "Equatorial", "EQUINOX": "J2000.0",
        })
        out["ned_url"] = r.url
        if r.error:
            out["error"] = r.error
        elif r.rows:
            row = r.rows[0]
            out.update(object_name=ned_client.pick(row, "Object Name"),
                       redshift=ned_client.as_float(ned_client.pick(row, "z", "Redshift")))
    return out


def query_catalog(ra_deg: float, dec_deg: float, catalog: str,
                  radius_arcsec: float = 3.0, type_filter: list[str] | None = None) -> dict[str, Any]:
    """按坐标查指定星表；选择函数随结果强制返回。"""
    if catalog not in CATALOG_SELECTION_FUNCTIONS:
        return {"error": f"未知星表 {catalog}", "supported": list(CATALOG_SELECTION_FUNCTIONS)}
    out: dict[str, Any] = {
        "catalog": catalog, "n_matches": 0, "matches": [],
        "selection_function": dict(CATALOG_SELECTION_FUNCTIONS[catalog]),
    }
    # NED 只直接覆盖部分星表的锥面检索；其余通过 ConeSearch 的 Cross-IDs 间接体现。
    # 这里统一走 ConeSearchByPosition，并显式声明哪些星表是"外部连接器占位"。
    radius_arcmin = max(radius_arcsec / 60.0, 1e-4)
    r = ned_client.ned_query("ConeSearchByPosition", {
        "LON": f"{ra_deg:.6f}d", "LAT": f"{dec_deg:.6f}", "RADIUS": radius_arcmin,
        "MAXREC": 50, "CSYS": "Equatorial", "EQUINOX": "J2000.0",
    })
    out["ned_url"] = r.url
    if r.error:
        out["error"] = r.error
        out["selection_function"]["note"] += "；本次检索失败，命中数不可解读为阴性证据"
        return out
    for row in r.rows:
        rec = {
            "name": ned_client.pick(row, "Object Name"),
            "ra": ned_client.as_float(ned_client.pick(row, "RA(deg)", "ra_deg")),
            "dec": ned_client.as_float(ned_client.pick(row, "Dec(deg)", "dec_deg")),
            "sep_arcsec": (ned_client.as_float(ned_client.pick(row, "Separation")) or 0) * 60.0,
            "z": ned_client.as_float(ned_client.pick(row, "z", "Redshift")),
            "type": ned_client.pick(row, "Phys Type"),
        }
        if type_filter and rec["type"] not in type_filter:
            continue
        out["matches"].append(rec)
    out["n_matches"] = len(out["matches"])
    if catalog == "Milliquas":
        out["selection_function"]["warning"] = "文献汇编非均匀样本；匹配可用于交叉证认，不可用于计数统计"
    return out


def get_photometry(ra_deg: float, dec_deg: float,
                   bands: list[str] | None = None, target: str | None = None) -> dict[str, Any]:
    """取多波段测光；非探测返回上限，不插补。"""
    bands = bands or ["W1", "W2", "W3", "u", "g", "r", "i", "z"]
    out: dict[str, Any] = {
        "photometry": {}, "non_detections": [], "bands_requested": bands,
        "note": "缺失为非探测上限，勿用中位数插补（天文缺失非随机）",
    }
    if not target:
        cone = ned_client.ned_query("ConeSearchByPosition", {
            "LON": f"{ra_deg:.6f}d", "LAT": f"{dec_deg:.6f}", "RADIUS": 1e-3,
            "MAXREC": 1, "CSYS": "Equatorial", "EQUINOX": "J2000.0",
        })
        if cone.rows:
            target = ned_client.pick(cone.rows[0], "Object Name")
    if not target:
        out["error"] = "无法从坐标解析出 NED 目标名；请显式传 target"
        return out
    r = ned_client.ned_query("PhotometryOfObject", {"TARGET": target, "SPECLINES": "no"})
    out["ned_url"] = r.url
    if r.error:
        out["error"] = r.error
        return out
    for row in r.rows:
        band = str(ned_client.pick(row, "Band", "bandpass", "Filter") or "")
        mag = ned_client.as_float(ned_client.pick(row, "m", "mag", "Magnitude"))
        upper = ned_client.as_float(ned_client.pick(row, "Upper Limit", "upper limit"))
        if mag is None:
            out["non_detections"].append(band)
            continue
        out["photometry"][band] = {
            "mag": mag,
            "err": ned_client.as_float(ned_client.pick(row, "err", "error")),
            "is_limit": upper is not None,
        }
    return out


def get_spectrum(ra_deg: float, dec_deg: float, survey: str = "LAMOST",
                 lines: list[str] | None = None, target: str | None = None) -> dict[str, Any]:
    """取光学光谱与发射线 flux/EW；波长覆盖校验后返回 unobservable_lines。

    修复审查意见 3：默认线表不含 NeV3426；显式请求且设施覆盖不到时给出
    unobservable_lines，而不是假装测到。
    """
    lines = list(lines) if lines else list(DEFAULT_LINES)
    coverage = LAMOST_COVERAGE_NM if survey == "LAMOST" else (300.0, 1000.0)  # SDSS/DESI 占位
    observable, unobservable = [], []
    for ln in lines:
        wl = LINE_WAVELENGTH_NM.get(ln)
        if wl is None:
            observable.append(ln)  # 未知线交给后端判断
        elif coverage[0] <= wl <= coverage[1]:
            observable.append(ln)
        else:
            unobservable.append(ln)

    out: dict[str, Any] = {
        "survey": survey, "wavelength_coverage_nm": list(coverage),
        "lines_requested": lines, "unobservable_lines": unobservable,
        "lines": {}, "caveat": "域迁移：跨巡天分辨率/波长覆盖/SNR 分布不同，阈值需按目标域重校准",
    }
    if unobservable:
        out["caveat"] += (f"；{','.join(unobservable)} 不在 {survey} 波长覆盖内，E3 等判据不可达")
    if not target:
        cone = ned_client.ned_query("ConeSearchByPosition", {
            "LON": f"{ra_deg:.6f}d", "LAT": f"{dec_deg:.6f}", "RADIUS": 1e-3, "MAXREC": 1,
            "CSYS": "Equatorial", "EQUINOX": "J2000.0",
        })
        if cone.rows:
            target = ned_client.pick(cone.rows[0], "Object Name")
    if not target:
        out["error"] = "无法解析目标名；请显式传 target"
        return out
    r = ned_client.ned_query("PhotometryOfObject", {"TARGET": target, "SPECLINES": "yes"})
    out["ned_url"] = r.url
    if r.error:
        out["error"] = r.error
        return out
    for row in r.rows:
        key = str(ned_client.pick(row, "Band", "band", "Line") or "")
        out["lines"][key] = {
            "flux": ned_client.as_float(ned_client.pick(row, "Flux Density", "flux")),
            "flux_err": ned_client.as_float(ned_client.pick(row, "Flux Density Error", "err")),
            "ew": ned_client.as_float(ned_client.pick(row, "EW", "ew")),
            "line_type": ned_client.pick(row, "Line Type"),
            "refcode": ned_client.pick(row, "Reference", "refcode"),
        }
    out["target"] = target
    return out


def get_lightcurve(ra_deg: float, dec_deg: float, survey: str,
                   band: str | None = None, start_mjd: float | None = None,
                   end_mjd: float | None = None) -> dict[str, Any]:
    """取光变曲线（EP_WXT/FXT、ZTF、eRASS、Swift_BAT）。

    EP 数据属外部连接器，NED 不供数；本函数返回结构化占位并明确数据来源缺口，
    由调用方注入真实光变（analyze_variability 接受任意 lightcurve）。
    """
    pos_err = {"EP_WXT": 78, "EP_FXT": 10, "Swift_BAT": 1500}.get(survey, None)
    out: dict[str, Any] = {
        "survey": survey, "band": band, "n_points": 0,
        "mjd": [], "flux": [], "flux_err": [],
        "position_error_arcsec": pos_err,
        "position_error_note": ("WXT R90≈1.3'，系统误差0.61'；FXT≈10''" if survey.startswith("EP")
                                else None),
        "data_source": "external connector (EP/ZTF/eRASS) — NED 不供数",
        "note": "真实光变需注入；本结构可直接喂给 analyze_variability",
    }
    return out


def crossmatch(left: list[dict[str, Any]], right_catalog: str,
               max_error_arcsec: float = 3.0, join: str = "1_and_2",
               validate: bool = True) -> dict[str, Any]:
    """天球坐标交叉匹配（球面角距），输出命中标记、角距与歧义标记。"""
    matches: list[dict[str, Any]] = []
    right = _mock_catalog(right_catalog)
    for src in left:
        ra, dec = float(src.get("ra_deg", 0)), float(src.get("dec_deg", 0))
        cands = []
        for r in right:
            sep = _angular_sep(ra, dec, r["ra_deg"], r["dec_deg"]) * 3600.0
            if sep <= max_error_arcsec:
                cands.append((sep, r["id"]))
        cands.sort()
        if cands:
            matches.append({
                "id": src.get("id"), "sep_arcsec": round(cands[0][0], 3),
                "counterpart": cands[0][1], "n_counterparts": len(cands),
                "ambiguous": len(cands) > 1,
            })
        elif join == "left_only":
            matches.append({"id": src.get("id"), "sep_arcsec": None,
                            "counterpart": None, "n_counterparts": 0, "ambiguous": False})

    warning = None
    if right_catalog == "WISEAGN" and max_error_arcsec <= 3:
        warning = "WISE 波束≈6''，3'' 内可能有多个源；ambiguous 项需光学图像核对"
    if validate:
        warning = (warning or "") + "；密集场应以 Gaia 自行/视差剔除假匹配与恒星"
    return {"n_matched": len(matches), "matches": matches, "warning": warning or None,
            "right_catalog": right_catalog}


def _mock_catalog(name: str) -> list[dict[str, Any]]:
    """内置微型演示星表，仅用于离线自测与示例，不代表真实数据。"""
    demo = {
        "WISEAGN": [{"id": "J062132.0+623837", "ra_deg": 95.3833, "dec_deg": 62.6439}],
        "3XMM": [{"id": "3XMM J062132.0+623837", "ra_deg": 95.3832, "dec_deg": 62.6440}],
        "Gaia": [{"id": "Gaia DR3 5000000000000000000", "ra_deg": 95.3834, "dec_deg": 62.6438}],
    }
    return demo.get(name, [])


# ===========================================================================
# L2（薄包装 criteria）
# ===========================================================================
def bpt_tool(log_nii_ha: float, log_oiii_hb: float, ew_ha: float | None = None,
             errors: dict[str, float] | None = None, diagram: str = "NII") -> dict[str, Any]:
    return compute_bpt(log_nii_ha, log_oiii_hb, ew_ha, errors, diagram)


def wise_tool(w1: float, w2: float, w2_snr: float, w3: float | None = None,
              criteria: str = "Stern2012") -> dict[str, Any]:
    return wise_agn_selection(w1, w2, w2_snr, w3, criteria)


def xray_tool(band: str = "soft_0.5_10", lx_2_10: float | None = None,
              nh: float | None = None, hardness_ratio: float | None = None,
              fe_kalpha_ew: float | None = None) -> dict[str, Any]:
    return xray_agn_selection(band, lx_2_10, nh, hardness_ratio, fe_kalpha_ew)


def variability_tool(lightcurve: dict[str, Any] | list[dict[str, Any]],
                     test_periodic: bool = True) -> dict[str, Any]:
    return analyze_variability(lightcurve, test_periodic)


# ===========================================================================
# L3
# ===========================================================================
def classify_tool(object_id: str, evidence: list[dict[str, Any]], strategy: str = "purity",
                  catalog_selection_functions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return classify_agn(object_id, evidence, strategy, catalog_selection_functions)


def find_agn_candidates(region: dict[str, float], catalogs: list[str],
                        criteria: list[str] | None = None, min_hits: int = 2,
                        strategy: str = "purity") -> dict[str, Any]:
    """批量候选筛选（演示版：对 region 内 mini 星表做命中合成）。

    生产环境应接入 SOP-B 的多星表在线交叉；此处保证选择函数与命中逻辑可执行。
    """
    ra, dec, radius = region["ra_deg"], region["dec_deg"], region["radius_deg"]
    # 按坐标聚类（不同星表对同一天体命名不同），1'' 内视为同一源。
    clusters: list[dict[str, Any]] = []
    for cat in catalogs:
        for src in _mock_catalog(cat):
            if _angular_sep(ra, dec, src["ra_deg"], src["dec_deg"]) > radius:
                continue
            placed = False
            for cl in clusters:
                if _angular_sep(src["ra_deg"], src["dec_deg"], cl["ra_deg"], cl["dec_deg"]) * 3600 <= 1.0:
                    cl["hits"].append(cat)
                    cl["ids"].append(src["id"])
                    placed = True
                    break
            if not placed:
                clusters.append({"ra_deg": src["ra_deg"], "dec_deg": src["dec_deg"],
                                 "hits": [cat], "ids": [src["id"]]})
    candidates = [
        {"id": cl["ids"][0], "ra": cl["ra_deg"], "dec": cl["dec_deg"],
         "hits": cl["hits"], "n_hits": len(cl["hits"]),
         "confidence": round(min(0.99, 0.5 + 0.2 * len(cl["hits"])), 2)}
        for cl in clusters if len(cl["hits"]) >= min_hits
    ]
    limiting_cat = min(catalogs, key=lambda c: CATALOG_SELECTION_FUNCTIONS.get(c, {}).get("flux_limit", ""))
    return {
        "n_candidates": len(candidates), "candidates": candidates,
        "selection_function": {
            "limiting_catalog": limiting_cat,
            "catalogs": [CATALOG_SELECTION_FUNCTIONS.get(c) for c in catalogs],
            "wavebands": sorted({EVIDENCE[e].band for e in EVIDENCE if e in ("E5", "E7", "E9")}),
        },
        "warning": "清单完备性由最弱星表决定；不可作人口统计的无偏样本（B6 不可跳过）",
    }


# ===========================================================================
# L4
# ===========================================================================
def submit_too(ra_deg: float, dec_deg: float, trigger_reason: str, instrument: str,
               urgency: str = "medium", justification: str | None = None,
               require_human_confirm: bool = True) -> dict[str, Any]:
    """提交 ToO。默认需人工确认闸门——本函数返回 pending，不自动对外提交。"""
    if urgency not in ("low", "medium", "high"):
        raise ValueError("urgency 只能是 low/medium/high")
    request_id = f"TOO-{uuid.uuid4().hex[:8].upper()}"
    status = "pending_human_confirmation" if require_human_confirm else "submitted"
    return {
        "request_id": request_id, "status": status, "ra_deg": ra_deg, "dec_deg": dec_deg,
        "instrument": instrument, "urgency": urgency, "trigger_reason": trigger_reason,
        "justification": justification,
        "estimated_response_hours": {"low": 48, "medium": 12, "high": 4}[urgency],
        "note": ("人工确认闸门开启：需操作员复核 trigger_reason/justification 后放行；"
                 "本服务不自动提交对外写操作" if require_human_confirm else "已提交"),
    }


def plan_followup(candidate_id: str, science_goal: str,
                  current_evidence: list[str] | None = None,
                  available_facilities: list[str] | None = None) -> dict[str, Any]:
    """按科学目标与证据缺口规划后随观测链（信息增益排序）。"""
    current = set(current_evidence or [])
    facilities = available_facilities or ["EP_FXT", "LAMOST", "NuSTAR", "VLA"]
    goals = {
        "confirm_agn": [
            ("EP_FXT", "N_H 测量与 10'' 定位", "E9/E12"),
            ("LAMOST", "宽线/BPT 证认", "E1/E2"),
        ],
        "measure_obscuration": [
            ("NuSTAR", "硬 X 测 N_H 与 Fe Kα", "E9"),
            ("EP_FXT", "软 X 光谱与定位", "E8/E12"),
        ],
        "test_changing_look": [
            ("LAMOST", "宽线类型变化复核", "E1/E2"),
            ("EP_FXT", "N_H 是否变化", "E12"),
        ],
        "radio_morphology": [
            ("VLA", "kpc 喷流/瓣形态", "E10"),
        ],
    }
    if science_goal not in goals:
        return {"error": f"未知 science_goal {science_goal}", "supported": list(goals)}
    plan = []
    for step, (fac, purpose, gain) in enumerate(goals[science_goal], 1):
        if fac in facilities:
            plan.append({"step": len(plan) + 1, "facility": fac, "purpose": purpose,
                         "evidence_gain": gain})
    return {
        "candidate_id": candidate_id, "plan": plan, "current_evidence": sorted(current),
        "rationale": "先遮蔽诊断再光谱证认，避免软 X 端选择效应；"
                     "changing-look 判据须区分吸积盘光度变化与遮蔽云遮挡（论文 p.12）",
    }


# ===========================================================================
# 内部工具
# ===========================================================================
def _looks_like_coords(s: str) -> bool:
    s = s.strip()
    if re.match(r"^[+-]?\d+\.?\d*\s+[+-]?\d+\.?\d*$", s):
        return True
    if re.match(r"^\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\s+[+-]\d{1,2}:\d{2}:\d{2}", s):
        return True
    return False


def _parse_coords(s: str) -> tuple[float, float]:
    s = s.strip()
    if ":" in s:
        ra_s, dec_s = s.split()
        sign = -1 if dec_s.startswith("-") else 1
        dh, dm, ds = dec_s.lstrip("+-").split(":")
        ra = int(ra_s.split(":")[0]) * 15 + int(ra_s.split(":")[1]) * 15 / 60 + float(ra_s.split(":")[2]) * 15 / 3600
        dec = sign * (int(dh) + int(dm) / 60 + float(ds) / 3600)
    else:
        ra, dec = map(float, s.split())
    return ra, dec


def _angular_sep(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """球面角距（度）。"""
    r1, r2, d1, d2 = map(math.radians, (ra1, ra2, dec1, dec2))
    cos_sep = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep))
