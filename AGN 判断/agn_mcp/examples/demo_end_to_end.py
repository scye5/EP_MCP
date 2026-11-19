"""端到端演示：S1 单源判定 A1→A9 完整跑一遍，打印每步结果。

无需 mcp，无需 pytest，直接运行：
    cd agn_mcp
    NED_OFFLINE=1 python examples/demo_end_to_end.py

NED_OFFLINE=1 用离线模式（不发网络请求）；去掉则走真实 NED API（需联网）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agn_mcp import tools as t  # noqa: E402

SEP = "=" * 68


def step(n: int, title: str, data: dict) -> None:
    print(f"\n[{n}] {title}")
    print("-" * 68)
    for k, v in data.items():
        if isinstance(v, list) and len(v) > 5:
            print(f"  {k}: {v[:5]} ... (共 {len(v)} 条)")
        else:
            print(f"  {k}: {v}")


def main() -> None:
    offline = os.environ.get("NED_OFFLINE", "0") == "1"
    print(SEP)
    print("AGN 判定服务 · S1 单源端到端演示（NGC 4151）")
    print(f"模式: {'离线' if offline else '真实 NED API'}")
    print(SEP)

    # A1 解析目标
    obj = t.resolve_object("NGC 4151", resolve_radius_arcsec=5)
    step(1, "A1 resolve_object — 名字/坐标解析 + 已知分类", obj)

    # 用标准坐标（离线模式下 NED 不返回，用 NGC 4151 的 J2000 坐标）
    ra, dec = 183.028, 39.405

    # A2 星表已有证认
    cat = t.query_catalog(ra, dec, "Milliquas", radius_arcsec=3)
    step(2, "A2 query_catalog — 已有光谱证认（Milliquas）", cat)

    # A3/A4 测光 + WISE 颜色
    phot = t.get_photometry(ra, dec, target="NGC 4151")
    step(3, "A3 get_photometry — 多波段测光", phot)
    wise = t.wise_tool(w1=15.6, w2=14.4, w2_snr=18)  # 演示值；真实流程喂 A3 的 W1/W2
    step(4, "A4 wise_agn_selection — WISE 颜色选源 (E5)", wise)

    # A5 X 射线
    xray = t.xray_tool(lx_2_10=8.4e42, nh=3e23, fe_kalpha_ew=0.3)
    step(5, "A5 xray_agn_selection — X 射线遮蔽分类 (E7/E8/E9)", xray)

    # A6/A7 光谱 + BPT
    spec = t.get_spectrum(ra, dec, "LAMOST", target="NGC 4151")
    step(6, "A6 get_spectrum — 光谱与发射线（含不可观测线提示）", {
        k: v for k, v in spec.items() if k in ("survey", "wavelength_coverage_nm", "unobservable_lines", "target")
    })
    bpt = t.bpt_tool(log_nii_ha=-0.35, log_oiii_hb=1.1, ew_ha=45)  # 演示值；真实流程喂 A6 谱线
    step(7, "A7 compute_bpt — BPT/WHAN 诊断 (E2/E4)", {
        "region": bpt["region"], "whan_class": bpt["whan_class"],
        "boundaries": bpt["boundaries"], "note": bpt["note"],
    })

    # A8 光变
    lc = t.get_lightcurve(ra, dec, "EP_WXT", band="0.5-4keV")
    step(8, "A8 get_lightcurve — 光变曲线容器", {
        k: v for k, v in lc.items() if k in ("survey", "position_error_arcsec", "data_source")
    })

    # A9 证据合成
    evidence = [
        {"id": "E5", "value": wise, "source": "NED PhotometryOfObject"},
        {"id": "E2", "value": bpt, "source": "compute_bpt", "refcode": "1997A&A...323...31K"},
        {"id": "E7", "value": {"lx_2_10": 8.4e42}, "source": "query_catalog 3XMM"},
    ]
    result = t.classify_tool(
        "NGC 4151", evidence, strategy="purity",
        catalog_selection_functions=[{"catalog": "3XMM", "flux_limit": "1e-14", "sky_coverage": "patchy"}],
    )
    print(f"\n[{9}] A9 classify_agn — 证据合成（核心）")
    print("-" * 68)
    print(f"  标签      : {result['label']}")
    print(f"  置信度    : {result['confidence']}")
    print(f"  总分      : {result['score']}")
    print(f"  采纳证据  : {[a['id'] for a in result['evidence_accepted']]}")
    print(f"  拒绝证据  : {[(r['id'], r['reason']) for r in result['evidence_rejected']]}")
    print(f"  选择函数  : {result['selection_function']}")
    print(f"  caveats   : {result['caveats']}")
    print(f"  决策轨迹  : {result['decision_trace']}")
    print(SEP)

    # 断言：确保演示结果符合预期
    assert result["label"] in ("CONFIRMED_AGN", "CANDIDATE_AGN"), result["label"]
    print("演示通过：标签落在预期范围。")


if __name__ == "__main__":
    main()
