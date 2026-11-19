"""AGN 判定证据体系：E1–E12 的唯一真值来源。

对齐主文档《AGN判定_MCP服务接口设计.md》v1.0 第 2 节。
本模块零依赖，可被 L2 判据层、L3 合成层与 MCP server 共同引用。

方法论依据：Hickox & Alexander 2018, ARA&A 56, 625。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EvidenceDef:
    """一条证据的静态定义。"""

    id: str
    band: str
    criterion: str
    threshold: str
    strength: str          # "strong" | "auxiliary"
    reliability: float | None
    completeness: float | None
    limitation: str
    reference: str

    @property
    def score(self) -> int:
        return 2 if self.strength == "strong" else 1


# ---------------------------------------------------------------------------
# E1–E12 证据表（主文档 2.1）
# ---------------------------------------------------------------------------
EVIDENCE: Final[dict[str, EvidenceDef]] = {
    "E1": EvidenceDef("E1", "optical", "Balmer 宽线 (Type 1)", "FWHM > 1000 km/s",
                      "strong", None, None, "需足够 S/N；低光度宽线弱", "Netzer 2015"),
    "E2": EvidenceDef("E2", "optical", "BPT 上支 AGN 区", "Kewley 实线之上",
                      "strong", None, None, "漏 LINER / 弱线；需四条线同 refcode 同孔径",
                      "Kauffmann 2003 / Kewley 2001"),
    "E3": EvidenceDef("E3", "optical", "高电离禁线 [Ne V] λ3426", "显著探测",
                      "strong", None, None, "342.6 nm 紫端；LAMOST 380–900 nm 覆盖不到",
                      "Veilleux & Osterbrock 1987"),
    "E4": EvidenceDef("E4", "optical", "WHAN 图", "EW(Hα) vs [N II]/Hα",
                      "auxiliary", None, None, "解 LINER 简并；非独立确认", "Cid Fernandes 2011"),
    "E5": EvidenceDef("E5", "infrared", "WISE 颜色", "W1−W2 ≥ 0.8 且 W2 < 15.5",
                      "auxiliary", 0.95, 0.78, "恒星形成污染；分不出遮蔽与否", "Stern 2012"),
    "E6": EvidenceDef("E6", "infrared", "中红外高电离禁线 [Ne VI]/[Ne V]", "显著探测",
                      "strong", None, None, "需中红外光谱，非测光", "Hickox & Alexander 2018 §2.3"),
    "E7": EvidenceDef("E7", "xray", "核区点源光度", "L_X(0.5–10 keV) > 1e42 erg/s",
                      "strong", None, None, "软波段受 N_H 压制，漏遮蔽", "论文 p.13/p.15"),
    "E8": EvidenceDef("E8", "xray", "遮蔽判据", "N_H > 1e22 cm^-2",
                      "auxiliary", None, None, "低计数无法约束 N_H；与光学分类一致率 80–90%", "论文 p.15"),
    "E9": EvidenceDef("E9", "xray", "Compton-thick", "N_H > 1.5e24 或 Fe Kα EW > 1 keV",
                      "strong", None, None, "需硬 X（BAT/NuSTAR）；计数少", "论文 p.13/p.15"),
    "E10": EvidenceDef("E10", "radio", "kpc 喷流/瓣 或 VLBI mas 核", "形态或亮温",
                       "strong", None, None, "只覆盖射电亮端，完备性极低", "Fanaroff & Riley 1974"),
    "E11": EvidenceDef("E11", "time", "非周期光变", "显著性 + 多波段相关",
                       "auxiliary", None, None, "瞬变/耀星污染，需 Gaia 剔除", "Ulrich 1997"),
    "E12": EvidenceDef("E12", "time", "吸收变化 vs 光度变化", "FXT 测得 N_H 是否变化",
                       "strong", None, None, "需后随光谱；完备性低", "论文 p.12"),
}

STRONG_IDS: Final[frozenset[str]] = frozenset(
    eid for eid, e in EVIDENCE.items() if e.strength == "strong"
)
AUX_IDS: Final[frozenset[str]] = frozenset(EVIDENCE) - STRONG_IDS

# 波段映射：独立性约束用——同一波段的多个判据只计一次最高分（主文档 2.3）。
BAND_OF: Final[dict[str, str]] = {eid: e.band for eid, e in EVIDENCE.items()}

LABELS: Final[tuple[str, ...]] = (
    "CONFIRMED_AGN",
    "CANDIDATE_AGN",
    "LIKELY_NON_AGN",
    "TRANSIENT_CANDIDATE",
    "INDETERMINATE",
)

# ---------------------------------------------------------------------------
# BPT 分界线（主文档审查意见第 2 条：写死，不用占位符）
# x = log10([N II]λ6584 / Hα), y = log10([O III]λ5007 / Hβ)
# ---------------------------------------------------------------------------
BPT_BOUNDARIES: Final[dict[str, str]] = {
    "kauffmann_2003": "y = 0.61/(x - 0.05) + 1.30",
    "kewley_2001": "y = 0.61/(x - 0.47) + 1.19",
    "schawinski_2007": "y = 1.05*x + 0.45",
}


def kauffmann_line(x: float) -> float:
    """Kauffmann et al. 2003 经验分界：线下为恒星形成区。"""
    return 0.61 / (x - 0.05) + 1.30


def kewley_line(x: float) -> float:
    """Kewley et al. 2001 最大星暴线：线上为 AGN/LINER。"""
    return 0.61 / (x - 0.47) + 1.19


def schawinski_line(x: float) -> float:
    """Schawinski et al. 2007 线：Kauffmann 线下、其上为 composite/LINER 分界参考。"""
    return 1.05 * x + 0.45


def score_of(evidence_id: str) -> int:
    """返回单条证据计分：强证据 2 分，辅助证据 1 分。未知 ID 记 0。"""
    e = EVIDENCE.get(evidence_id)
    return e.score if e else 0


def describe(evidence_id: str) -> str:
    e = EVIDENCE.get(evidence_id)
    if not e:
        return f"{evidence_id}: 未知证据"
    return f"{e.id} [{e.band}] {e.criterion} ({e.threshold}) 强度={e.strength} 分={e.score}"
