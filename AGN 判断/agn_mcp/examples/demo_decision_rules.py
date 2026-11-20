"""规则演示：把 classify_agn 的 5 类标签与关键规则逐个触发，看输出差异。

无需 mcp，直接运行：
    cd agn_mcp
    python examples/demo_decision_rules.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agn_mcp.decision import classify_agn  # noqa: E402

CASES = [
    ("两条强证据 → 确认", "X1", [
        {"id": "E1", "value": {"fwhm_kms": 3200}},
        {"id": "E7", "value": {"lx_2_10": 8e42}},
    ], "purity", None),
    ("仅 E5+E11 → 候选", "X2", [
        {"id": "E5", "value": {"is_candidate": True}},
        {"id": "E11", "value": {"is_variable": True}},
    ], "purity", None),
    ("BPT 稳定 SF → 否决", "X3", [
        {"id": "E2", "value": {"region": "SF"}},
    ], "purity", None),
    ("同样 SF，完备策略 → 不否决", "X3", [
        {"id": "E2", "value": {"region": "SF"}},
    ], "completeness", None),
    ("E9 遮蔽端特例：SF 也确认", "X4", [
        {"id": "E2", "value": {"region": "SF"}},
        {"id": "E9", "value": {"nh": 3e24}},
    ], "purity", None),
    ("LINER 无追加 → 证据不足", "X5", [
        {"id": "E2", "value": {"region": "LINER"}},
    ], "purity", None),
    ("LINER + WHAN → 候选", "X5", [
        {"id": "E2", "value": {"region": "LINER"}},
        {"id": "E4", "value": {"whan_class": "weak_agn"}},
    ], "purity", None),
    ("证据不足 → 不确定", "X6", [
        {"id": "E8", "value": {"nh": 1e22}},
    ], "purity", None),
]

print("=" * 72)
print("classify_agn 规则演示：同一判据在不同策略/证据组合下的输出")
print("=" * 72)
for desc, oid, evidence, strategy, sf in CASES:
    r = classify_agn(oid, evidence, strategy=strategy, catalog_selection_functions=sf)
    print(f"\n• {desc}")
    print(f"    策略={strategy}  →  标签={r['label']}  分数={r['score']}  置信={r['confidence']}")
    print(f"    轨迹: {r['decision_trace']}")
print("=" * 72)
print("全部 8 个用例执行完毕，无异常。")
