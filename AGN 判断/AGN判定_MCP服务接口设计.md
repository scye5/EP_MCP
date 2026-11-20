# 面向时域天文学的 AGN 判定：操作步骤与 MCP 服务接口设计

> 项目：面向时域天文学的 MCP 服务构建与协同观测应用研究
> 方法论依据：Hickox & Alexander 2018, ARA&A 56, 625（*Obscured Active Galactic Nuclei*，arXiv:1806.04680）
> 配套判据文献：Baldwin 1981 / Veilleux & Osterbrock 1987 / Kewley 2001 / Kauffmann 2003 / Cid Fernandes 2011 / Stern 2012 / Netzer 2015
> 版本：v1.0　日期：2026-11-19
> 说明：本文同时给出「人可按步骤执行的判定流程」与「可被 Agent 调用的 MCP 接口定义」，两者一一对应——每一步 SOP 都绑定一个具体工具。

---

## 1. 设计依据与原则

### 1.1 为什么这样设计

Hickox & Alexander (2018) 给出的核心框架直接决定了本服务的设计，而不是只作为参考文献挂在末尾：

- **p.8 定义了 reliability（排除非 AGN 污染的能力）与 completeness（选出全部 AGN 的能力），并明确二者不相关。** 极端例子是把所有星系都选上——completeness=100%，reliability≈0。→ 本服务把「纯度优先」与「完备优先」做成两套可切换的判定策略，不做默认值假设。
- **§2.5（p.21）原文：*"No single waveband provides a complete and reliable selection of AGN with current facilities."*** → 本服务禁止任何单一波段工具直接输出 `CONFIRMED`，必须有独立波段交叉。
- **§2.5 后半段：多波段用于建立给定体积内的近完备样本，单波段用于覆盖更大的亮度—红移空间，但必须知道 selection function，靠 forward modeling 从观测反推内禀分布。** → 批量统计类接口强制返回选择函数声明，拒绝输出"宇宙中 AGN 占比"这类无选择函数支撑的量。
- **p.23 Figure 9（引 Ricci 2017）：Swift-BAT 样本观测到的 Compton-thick 比例仅 8(+1/−2)%，修正选择效应后内禀为 27±4%；遮蔽比例（N_H>10²²）内禀 70±5%。** → 遮蔽端必须有专门的判据与修正路径，不能靠软 X 或光学外推。

### 1.2 三条硬原则

| 编号 | 原则 | 论文依据 | 在接口中的体现 |
|---|---|---|---|
| P1 | 单一波段不给确认结论 | §2.5 p.21 | `classify_agn` 强制要求 ≥2 条独立证据 |
| P2 | 纯度/完备分离声明 | p.8 | 每个判据标注 reliability/completeness，`classify_agn` 返回 `selection_function` |
| P3 | 遮蔽端独立覆盖 | p.18, p.23 | 硬 X / 中红外为独立工具链，不复用软 X 结果 |

### 1.3 三类科学场景（决定 SOP 分支）

| 场景 | 目标 | 主导数据 | 判定输出 |
|---|---|---|---|
| **S1 单源判定** | 判断某个已知天体是不是 AGN | 光谱 + 测光 + 星表 | `CONFIRMED / CANDIDATE / NON_AGN` |
| **S2 批量候选筛选** | 在给定天区找一批候选体 | 多星表交叉匹配 + 颜色 | 带命中标记与置信度的清单 |
| **S3 时域发现** | changing-look / 核区暂现 / 光变选源 | EP-WXT/FXT + ZTF + 光谱 | 活动性变化标签 + 后随观测建议 |

---

## 2. 判定证据体系（可编码的规则表）

### 2.1 证据清单

每条证据给出观测量、阈值、可靠性、完备性与出处。这是后续所有工具判据的唯一真值来源。

| ID | 波段 | 判据 | 阈值 | 强度 | Reliability | Completeness | 主要局限 | 出处 |
|---|---|---|---|---|---|---|---|---|
| E1 | 光学光谱 | Balmer 宽线（Type 1） | FWHM > 1000 km/s | 强 | 高 | 中（漏遮蔽） | 需信噪比够；低光度宽线弱 | Netzer 2015 |
| E2 | 光学光谱 | BPT 上支（AGN 区） | 越过 Kauffmann 虚线、Kewley 实线以上 | 强 | 高 | 低（漏 LINER/弱线） | [Ne V] 等禁线需要测到 | Kauffmann 2003 / Kewley 2001 |
| E3 | 光学光谱 | 高电离禁线 [Ne V] λ3426 | 显著探测 | 强 | 极高 | 低 | 紫端覆盖与 S/N 要求高 | Veilleux & Osterbrock 1987 |
| E4 | 光学光谱 | WHAN 图 | EW(Hα) 对 [N II]/Hα | 强 | 中高 | 中 | 解 LINER 简并，非独立确认 | Cid Fernandes 2011 |
| E5 | 中红外 | WISE 颜色 | W1−W2 ≥ 0.8 且 W2 < 15.5 | 中 | 95% | 78%（COSMOS） | 恒星形成污染；分不出遮蔽 | Stern 2012 |
| E6 | 中红外 | 高电离禁线 [Ne VI]7.6µm / [Ne V]14.3µm | 显著探测 | 强 | 高 | 高 | 需中红外光谱，非测光 | Hickox & Alexander 2018 §2.3 |
| E7 | 软 X 射线 | 核区点源光度 | L_X(0.5–10 keV) > 10⁴² erg/s | 强 | 高 | 中（漏遮蔽） | 软波段受 N_H 压制 | 论文 p.13/p.15 |
| E8 | X 射线 | 遮蔽判据 | N_H > 10²² cm⁻²（与光学分类一致率 80–90%） | 辅助 | 高 | — | 低计数无法约束 N_H | 论文 p.15 |
| E9 | 硬 X 射线 | Compton-thick | N_H > 1.5×10²⁴ cm⁻² 或 Fe Kα 6.4 keV EW > 1 keV | 强 | 高 | 低（计数少） | 需硬 X 波段（BAT/NuSTAR） | 论文 p.13/p.15 |
| E10 | 射电 | kpc 喷流/瓣 或 VLBI mas 级核 | 形态或亮温 | 强 | 高 | 极低（射电宁静占多数） | 只覆盖射电亮端 | Fanaroff & Riley 1974 |
| E11 | 时域 | 非周期光变，天–月时标，多波段相关 | 显著性 + 相关性 | 辅助 | 中 | 中 | 瞬变/耀星污染，需 Gaia 剔除 | Ulrich 1997 |
| E12 | 时域 | 吸收变化 vs 光度变化判别 | FXT 测得 N_H 是否变化 | 强（机制） | 中高 | 低 | 需后随光谱 | 论文 p.12（changing-look 机制） |

> **遮蔽端的专门说明（来自论文 p.18、p.23）**：Type 1 与 Type 2 类星体的中红外 SED 高度相似，**仅靠中红外颜色分不出遮蔽与否**，必须叠加光学或 X 射线。因此 E5 不能单独支撑"Type 2 / 遮蔽"结论。Compton-thick 内禀占比 27±4%，但 BAT 观测只有 8%——任何不含硬 X 的样本对这一端都是严重不完备的。

### 2.2 判定标签定义

| 标签 | 含义 | 准入条件 |
|---|---|---|
| `CONFIRMED_AGN` | 已确认 | ≥1 条强证据 且 总分 ≥3；或 ≥2 条强证据；且无强反证 |
| `CANDIDATE_AGN` | 候选体 | 总分 =2；或仅 E5 + E11（颜色 + 光变）；或 BPT LINER 区 + 任一独立支持 |
| `LIKELY_NON_AGN` | 倾向非 AGN | BPT 稳定落在 SF 区且无任何独立波段支持 |
| `TRANSIENT_CANDIDATE` | 时域暂现待证 | 光变触发但光谱未归类，需区分 changing-look / TDE / SN / 耀星 |
| `INDETERMINATE` | 证据不足 | 信噪比不够或波段覆盖缺失，不强行归类 |

### 2.3 证据合成规则（写进 `classify_agn` 的核心逻辑）

```
强度计分：强证据(E1,E2,E3,E6,E7,E9,E10,E12) = 2 分；辅助证据(E4,E5,E8,E11) = 1 分

一票否决：BPT 稳定 SF 区 + 无独立波段支持 → LIKELY_NON_AGN（不进入计分）

LINER 特殊规则：BPT 落 LINER 区时，禁止单独定性；必须追加 WHAN(E4) 或 X 射线(E7/E9) 才能升级到 CANDIDATE 以上
                 ——这是 Cid Fernandes 2011 解的那类简并（低光度 AGN vs 老年恒星族 retired galaxy）

遮蔽端规则：若 E9 成立，即使光学为 Type 2，仍按 CONFIRMED 处理

独立性约束：同一波段的多个判据只计一次最高分（例如 BPT 与其上的 [N II]/Hα 不叠加）
```

---

## 3. 具体操作步骤（SOP）

### 3.1 SOP-A：判断单个已知天体是不是 AGN

| 步骤 | 动作 | 调用工具 | 判据 / 输出 |
|---|---|---|---|
| A1 | 名字或坐标解析，查已知分类 | `resolve_object` | 得到标准坐标、红移、SIMBAD/NED 分类 |
| A2 | 已有光谱证认检查 | `query_catalog`（Milliquas / SDSS_QSO） | 若命中 confirmed QSO/Sy1/Sy2 → 直接给出结论，转 A8 复核 |
| A3 | 获取多波段测光 | `get_photometry` | WISE W1/W2/W3、SDSS ugriz、Gaia |
| A4 | WISE 颜色筛选 | `wise_agn_selection` | W1−W2 ≥ 0.8 → 中红外候选（辅助证据 E5） |
| A5 | 查 X 射线对应体 | `xray_agn_selection` | 软 X L_X、N_H、硬 X/Fe Kα → E7/E8/E9 |
| A6 | 取光谱并测线 | `get_spectrum` | 发射线 flux/EW 及误差 |
| A7 | BPT / WHAN 诊断 | `compute_bpt` | 区域标签（SF/composite/LINER/AGN）→ E2/E3/E4 |
| A8 | 光变与多波段一致性核查 | `get_lightcurve` + `analyze_variability` | 非周期光变、波段相关 → E11 |
| A9 | 证据合成 | `classify_agn` | 输出标签、置信度、证据清单、选择函数声明 |

> A2 的意义：SIMBAD/NED 的分类若带光谱引用，是成本最低的高置信结论。但注意分类来源——仅测光分类的不能当确认。**SIMBAD 与 NED 不一致时，以有光谱引用的那个为准。**

### 3.2 SOP-B：批量找 AGN 候选体

| 步骤 | 动作 | 调用工具 | 关键参数 |
|---|---|---|---|
| B1 | 定义天区 | — | 锥 Search（RA/Dec/radius）或矩形框 |
| B2 | 多星表在线交叉匹配 | `crossmatch` | 半径：光学 1–3″；WISE ≥3″；FXT 10″；WXT 1.3′ |
| B3 | 假匹配控制 | `crossmatch` 的 `validate` 选项 | 密集场用光学图像核对；Gaia 自行剔除恒星 |
| B4 | 颜色 + X 射线初筛 | `wise_agn_selection` / `xray_agn_selection` | 保纯度取交集，保完备取并集再筛 |
| B5 | 命中标记合成 | `find_agn_candidates` | ≥2 星表命中=高置信；单命中=候选 |
| B6 | 选择函数声明 | `find_agn_candidates` 返回字段 | 记录最弱星表的流量限与天区覆盖 |
| B7 | 导出清单 | — | CSV/FITS，供后续光谱申请 |

> **B6 不可跳过。** 交叉匹配的最终完备性由最弱的那个星表决定；这份清单可用于申请观测，但**不能当作无偏样本做人口统计**。

### 3.3 SOP-C：时域发现（EP 核心场景）

| 步骤 | 动作 | 调用工具 | 判据 / 输出 |
|---|---|---|---|
| C1 | WXT 光变/暂现触发 | `get_lightcurve`（survey=EP_WXT） | 软 X 显著变化，天–月时标 |
| C2 | 光学对应体匹配与污染剔除 | `crossmatch` + Gaia 自行/视差 | 排除耀星（WXT 1.3′ 定位假阳性高） |
| C3 | FXT ToO 后随光谱 | `submit_too` / `plan_followup` | 定位从 1.3′ 收紧到 10″ |
| C4 | 吸收 vs 光度变化判别 | `xray_agn_selection` + `compute_bpt` | N_H 未变 → 吸积盘光度变化；N_H 变 → 遮蔽变化（E12） |
| C5 | changing-look / TDE / SN 区分 | `classify_agn` | 宽线类型变化 + 光变曲线形态 |
| C6 | 多望远镜接力 | `plan_followup` | 光学光谱 + 硬 X + 射电证据链 |

> **论文 p.12 关键点**：changing-look 多数是吸积盘光度下降而非遮蔽云遮挡。C4 是区分二者的物理判据，也是把 EP 数据写进观测提案时的核心论证。
>
> **版本风险提示**：Hickox & Alexander 2018 早于 EP 发射（2024-01），全文无 EP。判据普适性引经典，仪器能力必须引 EP 团队最新标定/数据发布论文；两者不可混成一条引用。

### 3.4 SOP 决策流程

```
                    ┌─────────────┐
                    │ 输入天体/天区 │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
           S1 单源      S2 批量       S3 时域
              │            │            │
        查已知证认     多星表交叉     WXT 光变触发
              │            │            │
        测光+光谱      颜色+X射线     Gaia 剔除耀星
              │            │            │
        BPT/WHAN诊断   命中标记合成    FXT ToO 光谱
              │            │            │
        光变一致性     选择函数声明    N_H vs 光度判别
              │            │            │
              └────────────┼────────────┘
                           │
                  ┌────────▼────────┐
                  │ classify_agn 合成 │
                  │ 标签+置信度+选择函数│
                  └────────┬────────┘
                           │
              CONFIRMED / CANDIDATE / NON_AGN / TRANSIENT
                           │
                  需要后随 → submit_too / plan_followup
```

---

## 4. MCP 服务接口设计

### 4.1 服务架构与 MCP 原语映射

服务分四层，逐层对应 MCP 的三种原语：

| 层 | 职责 | MCP 原语 |
|---|---|---|
| L1 数据接入 | 星表查询、测光/光谱/光变获取 | Tools |
| L2 判据计算 | BPT、WISE、X 射线、光变分析 | Tools |
| L3 决策合成 | 证据合成、批量筛选 | Tools + Prompts |
| L4 协同观测 | ToO 提交、后随策略规划 | Tools |
| 知识层 | 判据表、文献库、星表清单 | Resources |

### 4.2 工具总览

| 工具名 | 层 | 一句话职责 |
|---|---|---|
| `resolve_object` | L1 | 名字/坐标 → 标准坐标与已知分类 |
| `query_catalog` | L1 | 按坐标查指定星表 |
| `get_photometry` | L1 | 取多波段测光 |
| `get_spectrum` | L1 | 取光谱与谱线测量 |
| `get_lightcurve` | L1 | 取光变曲线（EP/ZTF/eRASS） |
| `crossmatch` | L1 | 天球坐标交叉匹配 |
| `compute_bpt` | L2 | BPT/WHAN 诊断 |
| `wise_agn_selection` | L2 | WISE 颜色选源 |
| `xray_agn_selection` | L2 | X 射线选源与遮蔽分类 |
| `analyze_variability` | L2 | 光变特征与显著性 |
| `classify_agn` | L3 | 单源综合判定（核心） |
| `find_agn_candidates` | L3 | 批量候选体筛选 |
| `submit_too` | L4 | 提交机会观测请求 |
| `plan_followup` | L4 | 规划后随观测链 |

### 4.3 工具详细定义

以下 `inputSchema` 遵循 JSON Schema draft 2020-12，可直接用于 MCP `tools/list` 响应。`output` 为建议返回结构。

#### 4.3.1 `resolve_object`

```json
{
  "name": "resolve_object",
  "description": "解析天体名字或坐标，返回 J2000 标准坐标、红移与 SIMBAD/NED 已知分类；标注分类是否来自光谱引用。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "identifier": {"type": "string", "description": "天体名或 'RA Dec'（度）或 'HH:MM:SS ±DD:MM:SS'"},
      "resolve_radius_arcsec": {"type": "number", "default": 5}
    },
    "required": ["identifier"]
  }
}
```
```json
// output
{
  "resolved": true, "ra_deg": 0.0, "dec_deg": 0.0, "redshift": 0.0,
  "simbad_type": "QSO", "ned_type": "Sy1",
  "classification_has_spectral_ref": true,
  "references": ["bibcode", "..."],
  "conflict_note": "SIMBAD/NED 不一致时标注以光谱引用为准者"
}
```

#### 4.3.2 `query_catalog`

```json
{
  "name": "query_catalog",
  "description": "按坐标查询指定星表，返回命中源及其类型、红移、流量。星表选择函数随结果返回。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ra_deg": {"type": "number"},
      "dec_deg": {"type": "number"},
      "radius_arcsec": {"type": "number", "default": 3},
      "catalog": {
        "type": "string",
        "enum": ["Milliquas", "SDSS_QSO", "WISEAGN", "3XMM", "eRASS", "Swift_BAT", "FIRST", "NVSS"]
      },
      "type_filter": {"type": "array", "items": {"type": "string"}, "description": "如 ['Q','A','B']"}
    },
    "required": ["ra_deg", "dec_deg", "catalog"]
  }
}
```
```json
// output
{
  "catalog": "Milliquas", "n_matches": 1,
  "matches": [{"ra":0.0,"dec":0.0,"sep_arcsec":0.4,"type":"Q","z":1.23,"pQSO":0.99}],
  "selection_function": {"flux_limit": "...", "sky_coverage": "...", "z_range": "..."}
}
```
> Milliquas v8（Flesch 2023）约 102 万条，是文献汇编非均匀样本，**不可直接用于计数统计**；字段 `selection_function` 必须返回提示。

#### 4.3.3 `get_photometry`

```json
{
  "name": "get_photometry",
  "description": "取目标的多波段测光星等及误差；未探测到的波段返回上限而非插补值。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ra_deg": {"type": "number"},
      "dec_deg": {"type": "number"},
      "bands": {"type": "array", "items": {"type": "string"}, "default": ["W1","W2","W3","u","g","r","i","z"]}
    },
    "required": ["ra_deg", "dec_deg"]
  }
}
```
```json
// output
{"photometry": {"W1": {"mag":15.1,"err":0.03}, "W2": {"mag":14.4,"err":0.04}},
 "non_detections": ["W3"],
 "note": "缺失为非探测上限，勿用中位数插补（天文缺失非随机）"}
```

#### 4.3.4 `get_spectrum`

```json
{
  "name": "get_spectrum",
  "description": "取光学光谱并测发射线 flux/EW 及误差；返回波长覆盖、分辨率、S/N。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ra_deg": {"type": "number"},
      "dec_deg": {"type": "number"},
      "survey": {"type": "string", "enum": ["LAMOST","SDSS","DESI"], "default": "LAMOST"},
      "lines": {"type": "array", "items": {"type": "string"}, "default": ["Ha","Hb","NII6584","OIII5007","OI6300","SII6716","SII6731","NeV3426"]}
    },
    "required": ["ra_deg", "dec_deg"]
  }
}
```
```json
// output
{
  "wavelength_coverage_nm": [380, 900], "resolution_R": 1800, "sn_median": 12.5,
  "lines": {"Ha":{"flux":1.2e-16,"flux_err":5e-18,"ew":45.2,"ew_err":2.1}, "...":{}},
  "redshift": 0.043,
  "caveat": "域迁移：跨巡天分辨率/波长覆盖/SNR 分布不同，阈值需按目标域重校准"
}
```

#### 4.3.5 `get_lightcurve`

```json
{
  "name": "get_lightcurve",
  "description": "取多巡天光变曲线，含 EP-WXT/FXT、ZTF、eRASS；返回 MJD、流量与误差、波段。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ra_deg": {"type": "number"},
      "dec_deg": {"type": "number"},
      "survey": {"type": "string", "enum": ["EP_WXT","EP_FXT","ZTF","eRASS","Swift_BAT"]},
      "band": {"type": "string", "description": "如 '0.5-4keV'、'g'、'r'"},
      "start_mjd": {"type": "number"},
      "end_mjd": {"type": "number"}
    },
    "required": ["ra_deg", "dec_deg", "survey"]
  }
}
```
```json
// output
{"survey":"EP_WXT","band":"0.5-4keV","n_points":42,
 "mjd":[],"flux":[],"flux_err":[],
 "position_error_arcsec":78,"position_error_note":"WXT R90≈1.3'，系统误差0.61'；FXT≈10''"}
```
> EP 数据可用性：WXT 已构建 2024-08 至 2025-11 全天源表（约 4370 点源、16 万次探测）；FXT 首批数据 2025-12-11 公开（约 200 GB，HEASoft 兼容，入口 ep.bao.ac.cn）。

#### 4.3.6 `crossmatch`

```json
{
  "name": "crossmatch",
  "description": "天球坐标交叉匹配；输出命中标记与角距离，支持按波段设定匹配半径并做假匹配校验。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "left": {"type": "array", "items": {"type": "object", "properties": {"id":{"type":"string"},"ra_deg":{"type":"number"},"dec_deg":{"type":"number"}}}},
      "right_catalog": {"type": "string"},
      "max_error_arcsec": {"type": "number", "default": 3},
      "join": {"type": "string", "enum": ["1_and_2","1_or_2","left_only"], "default": "1_and_2"},
      "validate": {"type": "boolean", "default": true, "description": "密集场用光学图像/Gaia 自行核对，剔除假匹配"}
    },
    "required": ["left", "right_catalog"]
  }
}
```
```json
// output
{"n_matched":17,"matches":[{"id":"src-1","sep_arcsec":1.2,"n_counterparts":2,"ambiguous":true}],
 "warning": "WISE 波束≈6''，3'' 内可能有多个源；ambiguous 项需光学图像核对"}
```

#### 4.3.7 `compute_bpt`

```json
{
  "name": "compute_bpt",
  "description": "计算 BPT 线比并判定区域；LINER 区调用 WHAN 图辅助判别，输出证据标签。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "log_nii_ha": {"type": "number", "description": "log([N II]λ6584/Hα)"},
      "log_oiii_hb": {"type": "number", "description": "log([O III]λ5007/Hβ)"},
      "ew_ha": {"type": "number", "description": "Hα 等值宽度，用于 WHAN"},
      "errors": {"type": "object", "properties": {"log_nii_ha":{"type":"number"},"log_oiii_hb":{"type":"number"}}},
      "diagram": {"type": "string", "enum": ["NII","SII","OI"], "default": "NII"}
    },
    "required": ["log_nii_ha", "log_oiii_hb"]
  }
}
```
```json
// output
{"region":"LINER","kauffmann_below":false,"kewley_above":false,
 "whan_class":"retired","evidence_id":"E4",
 "note":"LINER 区禁止单独定性，需追加 WHAN 或 X 射线（Cid Fernandes 2011）",
 "boundaries":{"kauffmann_2003":"...","kewley_2001":"..."}}
```

#### 4.3.8 `wise_agn_selection`

```json
{
  "name": "wise_agn_selection",
  "description": "WISE 中红外颜色选源；返回候选标签、可靠性/完备性与遮蔽不可分辨的提示。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "w1": {"type": "number"}, "w2": {"type": "number"}, "w3": {"type": "number"},
      "w2_snr": {"type": "number"},
      "criteria": {"type": "string", "enum": ["Stern2012","Mateus2013"], "default": "Stern2012"}
    },
    "required": ["w1", "w2", "w2_snr"]
  }
}
```
```json
// output
{"is_candidate":true,"w1_minus_w2":0.93,"criteria":"Stern2012",
 "reliability":0.95,"completeness":0.78,
 "warning":"中红外颜色分不出遮蔽与否（论文 p.18），不可单独作为 Type 2 判据"}
```

#### 4.3.9 `xray_agn_selection`

```json
{
  "name": "xray_agn_selection",
  "description": "X 射线 AGN 选源与遮蔽分类；支持软/硬波段、N_H、Fe Kα EW 判据。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lx_2_10": {"type": "number", "description": "2-10 keV 光度 erg/s"},
      "nh": {"type": "number", "description": "柱密度 cm^-2"},
      "hardness_ratio": {"type": "number"},
      "fe_kalpha_ew": {"type": "number", "description": "6.4 keV 线 EW（keV）"},
      "band": {"type": "string", "enum": ["soft_0.5_10","hard_above10","BAT_14_195"], "default": "soft_0.5_10"}
    },
    "required": ["band"]
  }
}
```
```json
// output
{"is_agn":true,"is_obscured":true,"is_compton_thick":false,
 "criteria_used":["E7","E8"],
 "thresholds":{"lx":">1e42 erg/s","obscured_nh":">1e22 cm^-2","ct_nh":">1.5e24 cm^-2","fe_ka_ew":">1 keV"},
 "note":"软波段对 Compton-thick 基本无能为力；CT 内禀占比27±4%，BAT 观测仅8%（论文 p.23）"}
```

#### 4.3.10 `analyze_variability`

```json
{
  "name": "analyze_variability",
  "description": "分析光变显著性、幅度、时标与多波段相关性；输出是否变量及瞬变污染提示。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lightcurve": {"type": "object", "description": "get_lightcurve 的返回结构，可多条"},
      "test_periodic": {"type": "boolean", "default": true}
    },
    "required": ["lightcurve"]
  }
}
```
```json
// output
{"is_variable":true,"significance_sigma":6.2,"amplitude_mag":0.8,
 "timescale_days":45,"periodic":false,"cross_band_correlation":0.71,
 "evidence_id":"E11",
 "contamination_warning":"需 Gaia 自行/视差剔除耀星；短时标大振幅可能是 TDE/SN"}
```

#### 4.3.11 `classify_agn`（核心）

```json
{
  "name": "classify_agn",
  "description": "汇总多波段证据，按证据合成规则输出最终标签、置信度、证据清单与选择函数声明。禁止单一波段确认。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "object_id": {"type": "string"},
      "evidence": {"type": "array", "items": {
        "type": "object",
        "properties": {"id":{"type":"string","enum":["E1","E2","E3","E4","E5","E6","E7","E8","E9","E10","E11","E12"]},"value":{"type":"object"},"source":{"type":"string"}},
        "required": ["id"]
      }},
      "strategy": {"type": "string", "enum": ["purity","completeness"], "default": "purity",
                   "description": "purity=保精度取交集；completeness=保完备取并集"}
    },
    "required": ["object_id", "evidence"]
  }
}
```
```json
// output
{
  "label": "CONFIRMED_AGN",
  "confidence": 0.93,
  "score": 5,
  "evidence_accepted": ["E2","E7","E9"],
  "evidence_rejected": [{"id":"E5","reason":"与 E7 同属核区热辐射，独立性不足"}],
  "selection_function": {"wavebands":["optical","X-ray"],"flux_limits":"...","z_range":"..."},
  "caveats": ["未覆盖射电端","低光度端不完备"],
  "decision_trace": "E2(强,2)+E7(强,2)+E9(强,2) → 强证据≥2 → CONFIRMED"
}
```

#### 4.3.12 `find_agn_candidates`

```json
{
  "name": "find_agn_candidates",
  "description": "按天区与多星表做批量交叉筛选，输出带命中标记、置信度与选择函数声明的候选清单。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "region": {"type": "object", "properties": {"ra_deg":{"type":"number"},"dec_deg":{"type":"number"},"radius_deg":{"type":"number"}}},
      "catalogs": {"type": "array", "items": {"type": "string"}},
      "criteria": {"type": "array", "items": {"type": "string"}, "description": "如 ['W1-W2>0.8','Xray_point','BPT_AGN']"},
      "min_hits": {"type": "number", "default": 2},
      "strategy": {"type": "string", "enum": ["purity","completeness"], "default": "purity"}
    },
    "required": ["region", "catalogs"]
  }
}
```
```json
// output
{"n_candidates":234,"candidates":[{"id":"...","ra":0.0,"dec":0.0,"hits":["Milliquas","WISEAGN","3XMM"],"confidence":0.9,"z":0.4}],
 "selection_function":{"limiting_catalog":"3XMM","flux_limit":"...","sky_coverage":"...","z_range":"..."},
 "warning":"清单完备性由最弱星表决定；不可作人口统计的无偏样本"}
```

#### 4.3.13 `submit_too`

```json
{
  "name": "submit_too",
  "description": "提交目标机会（ToO）观测请求，返回请求编号与状态；需说明触发原因与紧急度。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "ra_deg": {"type": "number"}, "dec_deg": {"type": "number"},
      "trigger_reason": {"type": "string"},
      "urgency": {"type": "string", "enum": ["low","medium","high"]},
      "instrument": {"type": "string", "description": "如 EP_FXT、LAMOST、NuSTAR"},
      "justification": {"type": "string", "description": "引用判据与文献，作为提案论证"}
    },
    "required": ["ra_deg", "dec_deg", "trigger_reason", "instrument"]
  }
}
```
```json
// output
{"request_id":"TOO-2026-00123","status":"submitted","estimated_response_hours":12}
```

#### 4.3.14 `plan_followup`

```json
{
  "name": "plan_followup",
  "description": "基于当前证据缺口规划后随观测链，按信息增益排序推荐设施与观测顺序。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "candidate_id": {"type": "string"},
      "current_evidence": {"type": "array", "items": {"type": "string"}},
      "science_goal": {"type": "string", "enum": ["confirm_agn","measure_obscuration","test_changing_look","radio_morphology"]},
      "available_facilities": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["candidate_id", "science_goal"]
  }
}
```
```json
// output
{"plan":[
  {"step":1,"facility":"EP_FXT","purpose":"N_H 测量与 10'' 定位","evidence_gain":"E9/E12"},
  {"step":2,"facility":"LAMOST","purpose":"宽线/BPT 证认","evidence_gain":"E1/E2"}],
 "rationale":"先遮蔽诊断再光谱证认，避免软 X 端选择效应"}
```

### 4.4 Resources（只读知识资源）

| URI | 内容 |
|---|---|
| `agn://criteria/evidence_table` | 第 2.1 节证据表（机器可读） |
| `agn://criteria/decision_rules` | 第 2.3 节合成规则 |
| `agn://references/core` | 核心文献 bibcode 与引用要点 |
| `agn://catalogs/inventory` | 星表清单、流量限、选源函数与版本 |
| `agn://instruments/ep` | EP-WXT/FXT 参数、数据可用性、定位精度 |

### 4.5 Prompts（SOP 编排模板）

| 名称 | 编排内容 |
|---|---|
| `sop_single_object` | 驱动 A1→A9，逐步调用并在 A9 合成 |
| `sop_batch_search` | 驱动 B1→B7，强制 B6 选择函数声明 |
| `sop_time_domain` | 驱动 C1→C6，含 changing-look 机制判别 |
| `sop_followup` | 基于证据缺口生成后随提案论证文本 |

### 4.6 端到端调用示例（S1 单源）

```
1. resolve_object("EP J062132.0+623837")
      → ra/dec, z, SIMBAD: AGN?
2. get_photometry(ra, dec, ["W1","W2","W3"])
      → W1−W2 = 1.1
3. wise_agn_selection(w1,w2,w2_snr)
      → is_candidate=true (E5)
4. query_catalog(ra, dec, 3, "Swift_BAT")
      → 未命中 → 硬 X 缺失，遮蔽端不完备
5. get_spectrum(ra, dec, "LAMOST", ["Ha","Hb","NII6584","OIII5007"])
      → log([NII]/Hα), log([OIII]/Hβ), Hα FWHM
6. compute_bpt(...)
      → region=AGN (E2), 宽线 FWHM=3200 (E1)
7. get_lightcurve(ra, dec, "EP_WXT", "0.5-4keV", mjd_start, mjd_end)
   analyze_variability(...)
      → is_variable=true (E11)
8. classify_agn(object_id, evidence=[E5,E1,E2,E11], strategy="purity")
      → CONFIRMED_AGN, confidence 0.95,
        caveats=["硬 X 缺失，Compton-thick 端不完备"]
```

---

## 5. 协同观测闭环

把判定服务接入时域协同观测的完整闭环：

```
EP-WXT 发现光变/暂现
        │
        ▼
本服务 SOP-C：交叉匹配 + Gaia 剔除 + 初步分类
        │
        ├── 证据不足 ──► plan_followup 推荐观测链
        │                      │
        │                      ▼
        │              submit_too（EP-FXT / LAMOST / NuSTAR）
        │                      │
        │                      ▼
        │              新数据回流 → classify_agn 更新标签
        │
        └── 证据充分 ──► 发布候选体清单 → 申请光谱观测（SOP-B 输出）
```

EP 在其中的定位：**发现工具，不是证认工具**。WXT 抓变化（软 X，1.3′ 定位），FXT 做后随光谱（10″ 定位），最终证认仍要落到光学光谱或多波段一致性。1.3′ 的 WXT 定位在密集场交叉匹配假阳性很高，必须 FXT 跟进才能与光学/红外对应体安全匹配。

---

## 6. 不确定性与风险清单

| 风险 | 表现 | 缓解 | 论文/文献依据 |
|---|---|---|---|
| 选择效应叠加 | 交集样本对所有星表覆盖到的部分偏倚 | 返回 selection_function，禁止无偏统计宣称 | 论文 §2.5 p.21；p.23 Figure 9 |
| LINER 简并 | 低光度 AGN / 激波 / 老年恒星族在 BPT 重叠 | 强制 WHAN 或 X 射线追加 | Cid Fernandes 2011；论文 p.12 |
| 遮蔽端漏失 | 软 X / 光学漏掉 Compton-thick | 硬 X + 中红外独立工具链 | 论文 p.18/p.23（8% vs 27±4%） |
| 假匹配 | WISE 波束粗、WXT 定位粗 | 光学图像核对 + Gaia 自行剔除 | 仪器参数 |
| 域迁移 | SDSS 训练判据用于 LAMOST/DESI 性能悄悄下降 | 目标域留人工核验验证集重校准阈值 | 通用 ML 实践 |
| 标签循环 | 用 BPT 标签训练的模型学不到 BPT 之外的东西 | 引入 X 射线/WISE 独立标签交叉标注 | 通用 ML 实践 |
| 时间错配 | 经典文献早于 EP，无法为 EP 判据背书 | 判据引经典，仪器能力引 EP 新文献并标注 preprint | 论文 §6.1 无 EP |
| 缺失值误处理 | 天文缺失非随机（未探测到） | 保留上限，禁止中位数插补 | 巡天数据处理惯例 |

---

## 7. 参考文献

**方法论主文献**
1. Hickox & Alexander 2018, ARA&A 56, 625, *Obscured Active Galactic Nuclei
2. Netzer 2015, ARA&A 53, 365, *The Physics and Evolution of AGN*

**光学判据**
3. Baldwin, Phillips & Terlevich 1981, PASP 93, 5
4. Veilleux & Osterbrock 1987, ApJS 63, 295
5. Kewley et al. 2001, ApJ 556, 121（最大星暴线）
6. Kauffmann et al. 2003, MNRAS 346, 1055（经验分界线）
7. Cid Fernandes et al. 2011, MNRAS 403, 1036（WHAN 图）
8. Ho, Filippenko & Sargent 1997, ApJS 112, 315（LINER 基准）

**多波段判据**
9. Stern et al. 2012, ApJ 753, 30（WISE W1−W2≥0.8，78% 完备 / 95% 可靠）
10. Lacy et al. 2004, MNRAS 349, L43
11. Hickox et al. 2009, ApJ 696, 891（射电/X 射线/中红外样本 only modest overlap）
12. Fanaroff & Riley 1974, MNRAS 167, 31P

**光变与时域**
13. Ulrich, Maraschi & Urry 1997, ARA&A 35, 445（AGN 光变经典综述）
14. EP 团队 WXT 在轨标定论文（arXiv:2606.28101，1.3′ 定位精度）
15. EP J062132.0+623837 changing-look AGN 研究（arXiv:2610.30959，预印本，引用需标注）

**编目与工具**
16. Flesch 2023, Milliquas v8（约 102 万类星体/AGN/耀变体）
17. Schneider et al., SDSS Quasar Catalog
