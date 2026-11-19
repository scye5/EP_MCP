"""L2 判据计算层：BPT/WHAN、WISE 颜色、X 射线选源、光变分析。

全部为纯函数，零外部依赖，输入/输出为普通 dict，便于 MCP tool 直接包装与单测。
判据阈值来自主文档第 2.1 节证据表；BPT 三条分界线写死于 evidence.BPT_BOUNDARIES。
"""

from __future__ import annotations

import math
from typing import Any

from .evidence import (
    BPT_BOUNDARIES,
    kauffmann_line,
    kewley_line,
    schawinski_line,
)


# ---------------------------------------------------------------------------
# compute_bpt
# ---------------------------------------------------------------------------
def compute_bpt(
    log_nii_ha: float,
    log_oiii_hb: float,
    ew_ha: float | None = None,
    errors: dict[str, float] | None = None,
    diagram: str = "NII",
) -> dict[str, Any]:
    """BPT 线比分区；LINER 区附 WHAN 辅助。

    分区（主文档审查意见第 2 条）：
      - Kauffmann 线以下        -> SF（恒星形成）
      - Kauffmann 与 Kewley 之间 -> COMPOSITE
      - Kewley 线以上、Schawinski 线以下 -> LINER
      - Kewley 与 Schawinski 线均以上     -> AGN（Seyfert）

    对 NII 之外的 SII/OI 图，此处仅返回线比与占位说明，不一图双判。
    """
    x, y = float(log_nii_ha), float(log_oiii_hb)
    kauff = kauffmann_line(x)
    kewl = kewley_line(x)
    schaw = schawinski_line(x)

    kauffmann_below = y < kauff
    kewley_above = y >= kewl

    if diagram == "NII":
        if kauffmann_below:
            region = "SF"
        elif not kewley_above:
            region = "COMPOSITE"
        elif y < schaw:
            region = "LINER"
        else:
            region = "AGN"
    else:
        # SII/OI 图需各自的分界线，本服务当前只实现 NII；诚实返回 INDETERMINATE。
        region = "INDETERMINATE"

    whan_class = None
    if ew_ha is not None:
        whan_class = classify_whan(ew_ha, x)

    if region == "AGN":
        evidence_id = "E2"
        note = "Kewley 实线以上，落入 AGN/Seyfert 区（强证据 E2）。"
    elif region == "LINER":
        evidence_id = "E4"
        note = ("LINER 区禁止单独定性；须追加 WHAN(E4) 或 X 射线(E7/E9) "
                "才能升级到 CANDIDATE 以上（Cid Fernandes 2011）。")
    elif region == "COMPOSITE":
        evidence_id = "E4"
        note = "复合区：恒星形成与 AGN 混合，需独立波段追加证据。"
    elif region == "SF":
        evidence_id = None
        note = "Kauffmann 线以下，稳定落 SF 区；若无独立波段支持将触发一票否决。"
    else:
        evidence_id = None
        note = "当前仅实现 NII 图分界；SII/OI 请扩展分界线后使用。"

    if diagram != "NII":
        note = "本服务 BPT 仅实现 NII 图，SII/OI 返回 INDETERMINATE 而非猜测。"

    # 误差跨线的源不强行定性：若 y 的 ±1σ 触及 Kauffmann/Kewley 分界则标注不稳定。
    unstable = False
    if errors:
        ey = float(errors.get("log_oiii_hb", 0.0))
        if ey > 0 and min(abs(y - kauff), abs(y - kewl)) <= ey:
            unstable = True
        if unstable:
            note += " 注意：线比 ±1σ 跨分界，区域标签不稳定，合成时应下调权重。"

    return {
        "region": region,
        "log_nii_ha": x,
        "log_oiii_hb": y,
        "kauffmann_below": kauffmann_below,
        "kewley_above": kewley_above,
        "kauffmann_line_value": kauff,
        "kewley_line_value": kewl,
        "schawinski_line_value": schaw,
        "whan_class": whan_class,
        "evidence_id": evidence_id,
        "region_unstable": unstable,
        "note": note,
        "boundaries": dict(BPT_BOUNDARIES),
    }


def classify_whan(ew_ha: float, log_nii_ha: float) -> str:
    """WHAN 图（Cid Fernandes 2011）简化分类。

    - EW(Hα) < 3 Å                -> retired（老年恒星族，retired galaxy）
    - EW(Hα) ≥ 3 且 log[N II]/Hα < -0.2 -> sf
    - EW(Hα) ≥ 6 且 log[N II]/Hα ≥ -0.2 -> strong_agn
    - 其余（3 ≤ EW < 6 且 log ≥ -0.2）   -> weak_agn
    """
    if ew_ha < 3:
        return "retired"
    if log_nii_ha < -0.2:
        return "sf"
    if ew_ha >= 6:
        return "strong_agn"
    return "weak_agn"


# ---------------------------------------------------------------------------
# wise_agn_selection
# ---------------------------------------------------------------------------
def wise_agn_selection(
    w1: float,
    w2: float,
    w2_snr: float,
    w3: float | None = None,
    criteria: str = "Stern2012",
) -> dict[str, Any]:
    """WISE 中红外颜色选源。

    非探测或 SNR 不足时返回上限而非候选（主文档：天文缺失非随机，禁止插补）。
    """
    color = float(w1) - float(w2)
    if criteria == "Stern2012":
        threshold, w2_limit, snr_min, reliability, completeness = 0.8, 15.5, 5.0, 0.95, 0.78
    elif criteria == "Mateus2013":
        threshold, w2_limit, snr_min, reliability, completeness = 0.6, 15.5, 5.0, 0.90, 0.85
    else:
        raise ValueError(f"未知 WISE 判据: {criteria}")

    if float(w2_snr) < snr_min:
        return {
            "is_candidate": False,
            "status": "insufficient_snr",
            "w1_minus_w2": color,
            "w2_snr": float(w2_snr),
            "criteria": criteria,
            "thresholds": {"w1_minus_w2": threshold, "w2_mag_limit": w2_limit, "w2_snr_min": snr_min},
            "reliability": reliability,
            "completeness": completeness,
            "warning": "W2 SNR 不足，返回颜色测量值而非 AGN 候选；非探测不可当阴性证据。",
        }

    is_candidate = color >= threshold and float(w2) < w2_limit
    return {
        "is_candidate": is_candidate,
        "status": "measured",
        "w1_minus_w2": color,
        "w3_minus_w2": None if w3 is None else float(w3) - float(w2),
        "criteria": criteria,
        "thresholds": {"w1_minus_w2": threshold, "w2_mag_limit": w2_limit, "w2_snr_min": snr_min},
        "reliability": reliability,
        "completeness": completeness,
        "evidence_id": "E5" if is_candidate else None,
        "warning": "中红外颜色分不出遮蔽与否（论文 p.18），E5 为辅助证据，不可单独作为 Type 2 判据。",
    }


# ---------------------------------------------------------------------------
# xray_agn_selection
# ---------------------------------------------------------------------------
def xray_agn_selection(
    band: str = "soft_0.5_10",
    lx_2_10: float | None = None,
    nh: float | None = None,
    hardness_ratio: float | None = None,
    fe_kalpha_ew: float | None = None,
) -> dict[str, Any]:
    """X 射线 AGN 选源与遮蔽分类。

    E7: L_X(2–10 keV) > 1e42 erg/s；E8: N_H > 1e22；
    E9: N_H > 1.5e24 或 Fe Kα EW > 1 keV。
    遮蔽端（E9）为独立工具链，不复用软 X 结果（P3）。
    """
    lx_th, obscured_th, ct_th, fe_th = 1e42, 1e22, 1.5e24, 1.0

    is_agn = lx_2_10 is not None and float(lx_2_10) > lx_th
    is_obscured = nh is not None and float(nh) > obscured_th
    is_ct = (
        (nh is not None and float(nh) > ct_th)
        or (fe_kalpha_ew is not None and float(fe_kalpha_ew) > fe_th)
    )

    criteria_used: list[str] = []
    if is_agn:
        criteria_used.append("E7")
    if is_obscured:
        criteria_used.append("E8")
    if is_ct:
        criteria_used.append("E9")

    return {
        "is_agn": is_agn,
        "is_obscured": is_obscured,
        "is_compton_thick": is_ct,
        "criteria_used": criteria_used,
        "band": band,
        "hardness_ratio": hardness_ratio,
        "thresholds": {
            "lx": ">1e42 erg/s",
            "obscured_nh": ">1e22 cm^-2",
            "ct_nh": ">1.5e24 cm^-2",
            "fe_ka_ew": ">1 keV",
        },
        "note": (
            "E9(Compton-thick) 为强证据且触发遮蔽端特殊规则；软波段对 CT 基本无能为力。"
            "CT 内禀占比 27±4%，BAT 观测仅 8%（论文 p.23）。"
        ),
    }


# ---------------------------------------------------------------------------
# analyze_variability
# ---------------------------------------------------------------------------
def analyze_variability(
    lightcurve: dict[str, Any] | list[dict[str, Any]],
    test_periodic: bool = True,
) -> dict[str, Any]:
    """光变显著性、幅度、时标与多波段相关性（E11）。

    显著性采用加权常数模型 χ² 的约化量近似；周期检验留接口（真实 Lomb-Scargle
    需 astropy，此处返回 periodic=False 并注明，不伪造周期结论）。
    """
    curves = lightcurve if isinstance(lightcurve, list) else [lightcurve]
    results: list[dict[str, Any]] = []
    sigmas: list[float] = []
    amplitudes: list[float] = []
    spans: list[float] = []

    for lc in curves:
        mjd = [float(v) for v in lc.get("mjd", [])]
        flux = [float(v) for v in lc.get("flux", [])]
        err = [float(v) for v in lc.get("flux_err", [])] or [1.0] * len(flux)
        n = min(len(mjd), len(flux), len(err))
        if n < 3:
            results.append({"band": lc.get("band"), "n_points": n, "significance_sigma": 0.0,
                            "status": "insufficient_points"})
            continue
        mjd, flux, err = mjd[:n], flux[:n], err[:n]
        w = [1.0 / (e * e) if e > 0 else 1.0 for e in err]
        sw = sum(w)
        mean = sum(f * wi for f, wi in zip(flux, w)) / sw
        chi2 = sum(((f - mean) / e) ** 2 for f, e in zip(flux, err) if e > 0)
        dof = n - 1
        red_chi2 = chi2 / dof if dof > 0 else 0.0
        sig = math.sqrt(max(chi2 - dof, 0.0)) if chi2 > dof else 0.0
        amp = max(flux) - min(flux)
        span = max(mjd) - min(mjd)
        results.append({
            "band": lc.get("band"), "n_points": n, "significance_sigma": round(sig, 2),
            "reduced_chi2": round(red_chi2, 2), "amplitude_flux": round(amp, 6),
            "timescale_days": round(span, 2), "status": "ok",
        })
        sigmas.append(sig)
        amplitudes.append(amp)
        spans.append(span)

    best_sig = max(sigmas, default=0.0)
    is_variable = best_sig >= 3.0
    cross_corr = None
    if len(curves) >= 2:
        cross_corr = _pearson(curves[0].get("flux", []), curves[1].get("flux", []))

    return {
        "is_variable": is_variable,
        "significance_sigma": round(best_sig, 2),
        "amplitude_mag": None,  # 输入为流量，未给零点；需要星等输入时才填
        "timescale_days": round(max(spans), 2) if spans else None,
        "periodic": False,
        "cross_band_correlation": None if cross_corr is None else round(cross_corr, 3),
        "evidence_id": "E11" if is_variable else None,
        "per_band": results,
        "contamination_warning": (
            "需 Gaia 自行/视差剔除耀星；短时标大振幅可能是 TDE/SN。"
            "本函数未做周期检验（periodic 恒为 False 是诚实占位，非阴性结论）。"
            if test_periodic else
            "需 Gaia 自行/视差剔除耀星；短时标大振幅可能是 TDE/SN。"
        ),
    }


def _pearson(a: list[Any], b: list[Any]) -> float | None:
    n = min(len(a), len(b))
    if n < 3:
        return None
    xa = [float(v) for v in a[:n]]
    xb = [float(v) for v in b[:n]]
    ma, mb = sum(xa) / n, sum(xb) / n
    num = sum((u - ma) * (v - mb) for u, v in zip(xa, xb))
    da = math.sqrt(sum((u - ma) ** 2 for u in xa))
    db = math.sqrt(sum((v - mb) ** 2 for v in xb))
    return num / (da * db) if da > 0 and db > 0 else None
