"""AGN 判定服务单元测试（仅用 unittest，无需 pytest）。

运行：
    cd agn_mcp
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agn_mcp.criteria import (  # noqa: E402
    analyze_variability,
    classify_whan,
    compute_bpt,
    wise_agn_selection,
    xray_agn_selection,
)
from agn_mcp.decision import classify_agn  # noqa: E402
from agn_mcp import tools  # noqa: E402


class TestBPT(unittest.TestCase):
    def test_four_regions(self):
        self.assertEqual(compute_bpt(-1.0, -0.5)["region"], "SF")
        self.assertEqual(compute_bpt(-0.4, 0.1)["region"], "COMPOSITE")
        self.assertEqual(compute_bpt(0.0, 0.2)["region"], "LINER")
        self.assertEqual(compute_bpt(-0.3, 1.0)["region"], "AGN")

    def test_boundaries_written(self):
        b = compute_bpt(-0.3, 1.0)["boundaries"]
        self.assertIn("kauffmann_2003", b)
        self.assertIn("kewley_2001", b)
        self.assertIn("schawinski_2007", b)

    def test_liner_needs_support_note(self):
        r = compute_bpt(0.0, 0.2)
        self.assertIn("WHAN", r["note"])
        self.assertEqual(r["evidence_id"], "E4")

    def test_whan(self):
        self.assertEqual(classify_whan(2, 0.3), "retired")
        self.assertEqual(classify_whan(5, -0.5), "sf")
        self.assertEqual(classify_whan(8, 0.3), "strong_agn")
        self.assertEqual(classify_whan(4, 0.3), "weak_agn")

    def test_unstable_crossing(self):
        r = compute_bpt(-0.3, 0.40, errors={"log_oiii_hb": 0.3})
        self.assertTrue(r["region_unstable"])


class TestWISE(unittest.TestCase):
    def test_threshold(self):
        self.assertTrue(wise_agn_selection(15.6, 14.4, 18)["is_candidate"])
        self.assertFalse(wise_agn_selection(15.1, 14.4, 18)["is_candidate"])

    def test_low_snr_returns_limit(self):
        r = wise_agn_selection(15.6, 14.4, 3)
        self.assertEqual(r["status"], "insufficient_snr")
        self.assertFalse(r["is_candidate"])

    def test_obscuration_warning(self):
        self.assertIn("遮蔽", wise_agn_selection(15.6, 14.4, 18)["warning"])


class TestXray(unittest.TestCase):
    def test_e7_e8_e9(self):
        r = xray_agn_selection(lx_2_10=8e42, nh=3e24, fe_kalpha_ew=1.2)
        self.assertIn("E7", r["criteria_used"])
        self.assertIn("E8", r["criteria_used"])
        self.assertIn("E9", r["criteria_used"])
        self.assertTrue(r["is_compton_thick"])

    def test_soft_band_not_ct(self):
        r = xray_agn_selection(lx_2_10=8e42, nh=1e21)
        self.assertFalse(r["is_compton_thick"])
        self.assertFalse(r["is_agn"] is False)  # E7 成立


class TestVariability(unittest.TestCase):
    def test_variable(self):
        lc = {"mjd": [1, 2, 3, 4, 5], "flux": [1, 5, 1, 5, 1], "flux_err": [0.1] * 5,
              "band": "g"}
        r = analyze_variability(lc)
        self.assertTrue(r["is_variable"])
        self.assertEqual(r["evidence_id"], "E11")

    def test_insufficient_points(self):
        r = analyze_variability({"mjd": [1, 2], "flux": [1, 2], "flux_err": [0.1, 0.1]})
        self.assertFalse(r["is_variable"])


class TestClassify(unittest.TestCase):
    def test_two_strong_confirmed(self):
        r = classify_agn("X", [
            {"id": "E1", "value": {"fwhm_kms": 3200}},
            {"id": "E7", "value": {"lx_2_10": 8e42}},
        ], catalog_selection_functions=[{"catalog": "3XMM", "flux_limit": "1e-14"}])
        self.assertEqual(r["label"], "CONFIRMED_AGN")
        self.assertGreaterEqual(r["score"], 4)

    def test_e9_exception_overrides_sf(self):
        """审查意见 1/5：E9 成立即使 BPT SF 也应 CONFIRMED，SF 否决豁免。"""
        r = classify_agn("CT", [
            {"id": "E2", "value": {"region": "SF"}},
            {"id": "E9", "value": {"nh": 3e24}},
        ])
        self.assertEqual(r["label"], "CONFIRMED_AGN")
        self.assertIn("豁免", r["decision_trace"])

    def test_sf_veto(self):
        r = classify_agn("SF", [{"id": "E2", "value": {"region": "SF"}}])
        self.assertEqual(r["label"], "LIKELY_NON_AGN")
        self.assertIn("一票否决", r["decision_trace"])

    def test_sf_veto_completeness_keeps_pending(self):
        r = classify_agn("SF", [{"id": "E2", "value": {"region": "SF"}}],
                         strategy="completeness")
        self.assertNotEqual(r["label"], "LIKELY_NON_AGN")

    def test_liner_alone_indeterminate(self):
        r = classify_agn("LIN", [{"id": "E2", "value": {"region": "LINER"}}])
        self.assertEqual(r["label"], "INDETERMINATE")

    def test_liner_with_whan_candidate(self):
        r = classify_agn("LIN", [
            {"id": "E2", "value": {"region": "LINER"}},
            {"id": "E4", "value": {"whan_class": "weak_agn"}},
        ])
        self.assertEqual(r["label"], "CANDIDATE_AGN")

    def test_independence_same_band(self):
        """E1/E2 同属 optical，只计最高分一次。"""
        r = classify_agn("X", [
            {"id": "E1", "value": {"fwhm_kms": 3200}},
            {"id": "E3", "value": {"detected": True}},
            {"id": "E7", "value": {"lx_2_10": 8e42}},
        ])
        rejected_ids = [x["id"] for x in r["evidence_rejected"]]
        self.assertTrue(any("E3" in str(i) or "E1" in str(i) for i in rejected_ids) or
                        len(r["evidence_accepted"]) <= 2)

    def test_spectral_ref_gate(self):
        """审查意见 4：无光谱引用的分类证据不得在 purity 下升强。"""
        r = classify_agn("X", [
            {"id": "E1", "value": {"fwhm_kms": 3200}, "source": "NED classification",
             "spectral_ref": False},
            {"id": "E7", "value": {"lx_2_10": 8e42}},
        ])
        self.assertNotEqual(r["label"], "CONFIRMED_AGN")

    def test_selection_function_caveat(self):
        r = classify_agn("X", [{"id": "E7", "value": {"lx_2_10": 8e42}}])
        self.assertFalse(r["selection_function"]["provided"])
        self.assertTrue(any("人口统计" in c for c in r["caveats"]))

    def test_transient_candidate(self):
        lc = {"mjd": [1, 2, 3, 4, 5], "flux": [1, 5, 1, 5, 1], "flux_err": [0.1] * 5}
        var = analyze_variability(lc)
        r = classify_agn("T", [{"id": "E11", "value": var}])
        self.assertEqual(r["label"], "TRANSIENT_CANDIDATE")

    def test_e5_plus_e11_is_candidate_not_transient(self):
        """E5+E11 按 2.2 是 CANDIDATE（颜色+光变），不应被暂现规则拦截。"""
        r = classify_agn("T2", [
            {"id": "E5", "value": {"is_candidate": True}},
            {"id": "E11", "value": {"is_variable": True}},
        ])
        self.assertEqual(r["label"], "CANDIDATE_AGN")


class TestTools(unittest.TestCase):
    def test_spectrum_unobservable_line(self):
        sp = tools.get_spectrum(95.38, 62.64, "LAMOST", ["Ha", "NeV3426"], target="M81")
        self.assertIn("NeV3426", sp["unobservable_lines"])

    def test_spectrum_default_excludes_nev(self):
        sp = tools.get_spectrum(95.38, 62.64, "LAMOST", target="M81")
        self.assertNotIn("NeV3426", sp["lines_requested"])

    def test_catalog_selection_function(self):
        r = tools.query_catalog(95.38, 62.64, "Milliquas")
        self.assertIn("selection_function", r)
        self.assertIn("不可", r["selection_function"]["note"])

    def test_crossmatch_ambiguous(self):
        r = tools.crossmatch([{"id": "s", "ra_deg": 95.3833, "dec_deg": 62.6439}], "WISEAGN", 3)
        self.assertGreaterEqual(r["n_matched"], 1)

    def test_submit_too_human_gate(self):
        r = tools.submit_too(1, 2, "flare", "EP_FXT")
        self.assertEqual(r["status"], "pending_human_confirmation")

    def test_plan_followup(self):
        r = tools.plan_followup("x", "measure_obscuration")
        self.assertIn("NuSTAR", [p["facility"] for p in r["plan"]])

    def test_server_specs(self):
        from agn_mcp.server import tool_specs
        names = [s["name"] for s in tool_specs()]
        self.assertEqual(len(names), 14)
        self.assertIn("classify_agn", names)


if __name__ == "__main__":
    unittest.main()
