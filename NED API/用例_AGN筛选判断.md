# 用例：AGN 筛选判断（S1 单源，NED 后端实现）

- 日期：2026-11-19
- 所属项目：面向时域天文学的 MCP 服务构建与协同观测应用研究
- **主文档**：`D:/86183/桌面/AGN 判断/AGN判定_MCP服务接口设计.md`（v1.0）。本文不是另一套设计，是它的 `sop_single_object` 执行实例，补齐 NED 作为 L1 数据后端时的字段映射与证据链规则。
- 对齐项：14 个工具名、证据 ID E1–E12、五类标签、`purity`/`completeness` 策略、选择函数强制声明。

## 0. 目标与边界

给定时域警报的一个坐标，走 A1→A9 判定该位置是否为 AGN，输出主文档定义的标签、置信度、证据清单和选择函数声明。

**边界**：NED 回答"这个位置是不是已知 AGN、有没有光谱和多波段证据"，不回答"这次变亮是不是 AGN 耀发"。后者属 S3 时域分支，靠 E11/E12，NED 的静态数据给不出结论。输出中这两类判断必须分字段写，不能合成一个标签。

## 1. NED 到证据 ID 的映射（本文核心）

这是主文档缺失的一张表：E1–E12 中哪些能由 NED 直接供数，哪些必须外部补。不能把 NED 返回"无记录"当成证据否定。

| 证据 ID | NED 能否供数 | 取数路径 | 备注 |
|---|---|---|---|
| E1 宽 Balmer 线 | 部分 | `PhotometryOfObject?SPECLINES=yes`，Line Type 标 BEL 或文献描述 broad component | NED 存流量与线型标记，不存 FWHM；要 FWHM>1000 km/s 的定量判据必须走 `get_spectrum` |
| E2 BPT | 部分 | 谱线流量同上，交给 `compute_bpt` | **四条线必须同 refcode 同孔径**；跨文献凑线比是主要错误源 |
| E3 [Ne V] λ3426 | 少见 | 谱线表检索 | 342.6 nm，LAMOST 380–900 nm 覆盖不到（见第 5 节问题 3） |
| E4 WHAN | 通常不能 | NED 详细测光一般不含 EW(Hα) | 需 `get_spectrum` 补 EW，再从 `agn://criteria/decision_rules` 取规则 |
| E5 WISE 颜色 | 能 | `PhotometryOfObject` 宽带测光，筛 bandpass = AllWISE W1/W2，取总流量 | 传 `wise_agn_selection`；非探测必须传上限，不可插补 |
| E6 中红外高电离禁线 | 基本不能 | — | 走中红外光谱设施，NED 无对应结构化字段 |
| E7 软 X 核区光度 | 只能定性 | `CrossidsOfObject` 中 XrayS 前缀 + EM Region | NED 不存 L_X；定量必须 `query_catalog("3XMM"/"eRASS")` |
| E8 N_H | 不能 | — | `xray_agn_selection` |
| E9 Compton-thick | 不能 | — | `query_catalog("Swift_BAT")` + `xray_agn_selection` |
| E10 射电形态 | 部分 | `CrossidsOfObject` 中 RadioS/NLRG/BLRG/FSRQ 前缀 | NED 给证认不给形态；喷流/瓣结构需图像 |
| E11 光变 | 不能 | — | `get_lightcurve` + `analyze_variability` |
| E12 吸收 vs 光度变化 | 不能 | — | FXT 后随光谱，属 SOP-C |

补充：NED 的 `OverviewOfObject` 与 `ClassificationsOfObject` 提供一类**主文档未单列的先验证据**——Activity Type 的文献分类（Sy1.x/Sy2/NLSy1/BLLAC/QSO/LINER/RET/PAS 等）。它可映射到 E1/E2，但必须走 `resolve_object` 的 `classification_has_spectral_ref` 标记；只有测光分类或分类来源无光谱引用时，不得升为强证据。

## 2. 输入 / 输出（对齐主文档 4.3.11）

`classify_agn` 输入：

```json
{
  "object_id": "NGC 4151",
  "evidence": [
    {"id": "E5", "value": {"w1": 15.1, "w2": 14.4, "w2_snr": 18}, "source": "NED PhotometryOfObject", "refcode": "..."},
    {"id": "E2", "value": {"log_nii_ha": -0.35, "log_oiii_hb": 1.1}, "source": "NED SPECLINES=yes", "refcode": "..."},
    {"id": "E7", "value": {"catalog": "3XMM", "lx_2_10": 8.4e42}, "source": "query_catalog"}
  ],
  "strategy": "purity",
  "catalog_selection_functions": [
    {"catalog": "3XMM", "flux_limit": "...", "sky_coverage": "...", "z_range": "..."}
  ]
}
```

输出沿用主文档 `classify_agn` 的 `label / confidence / score / evidence_accepted / evidence_rejected / selection_function / caveats / decision_trace`。额外要求 `evidence_accepted` 中每条带 `refcode`，缺失时标 `refcode: null` 且来源层级降为"文献分类无光谱引用"。

## 3. A1→A9 的 NED 实现序列

| SOP 步 | 主文档工具 | NED 侧调用 | 产出 |
|---|---|---|---|
| A1 | `resolve_object` | `ConeSearchByPosition`（`RADIUS` 单位 arcmin）+ `OverviewOfObject` | J2000 坐标、z、Object Type、Cross-IDs 子集、误差椭圆；注意 Object Type=`G` 不能排除 AGN |
| A2 | `query_catalog` | `ClassificationsOfObject` 的 Activity Type + NED Homogenized Classification 及 Flag | 先验分类；有光谱引用者可直接进强证据 |
| A3 | `get_photometry` | `PhotometryOfObject`（`SPECLINES=no`） | WISE/SDSS/2MASS 测光，含上下限与孔径类型 |
| A4 | `wise_agn_selection` | 由 A3 的 W1/W2 喂入 | E5，w2_snr 不足时返回上限而非候选 |
| A5 | `xray_agn_selection` | `CrossidsOfObject` 给 XrayS 定性；`query_catalog` 给 L_X/N_H 定量 | E7/E8/E9；缺硬 X 必须在 caveats 声明遮蔽端不完备 |
| A6 | `get_spectrum` | `PhotometryOfObject?SPECLINES=yes` 或 LAMOST/SDSS/DESI | flux/EW/Line Type/Aperture Type/refcode |
| A7 | `compute_bpt` | A6 四条同孔径线 + EW(Hα) | E2/E4；LINER 区强制 WHAN 或 X 射线追加 |
| A8 | `get_lightcurve` + `analyze_variability` | NED 不供数 | E11；Gaia 自行剔除耀星 |
| A9 | `classify_agn` | 汇总，执行主文档 2.3 合成规则 | 标签 + 置信度 + selection_function |

## 4. Worked example：NGC 4151

用来说明为什么 A1 的 Object Type 不能当结论。

1. A1：`resolve_object("NGC 4151")` → NED Object Type = `G`。若只看这一项会误判为普通星系。
2. A2：`ClassificationsOfObject` → Activity Type = `Sy1.5`，带文献引用；NED Homogenized Classification 一致。作为 E1/E2 先验强证据。
3. `CrossidsOfObject` → 同名条目分别带 `IrS`、`RadioS`、`VisS`、`XrayS` 前缀，对应 E7 定性与 E10 部分证据。
4. A6：`PhotometryOfObject?SPECLINES=yes` → 宽 Balmer 线与高激发 [O III]，E1 命中；同文献同孔径取四条线。
5. A7：`compute_bpt` → AGN 区，E2。
6. A9：E1+E2+E7 → 强证据≥2，`CONFIRMED_AGN`，confidence ≥ 0.9；caveats 注明"硬 X 未覆盖，Compton-thick 端不完备"。

若输入换成 NGC 4151 核区的一条新警报，A1–A9 仍得 `CONFIRMED_AGN`，但**不能**据此说本次增亮是 AGN 耀发。是否 changing-look/TDE/SN 需走 SOP-C 的 E11/E12，写在独立字段。

## 5. 对 v1.0 接口的审查意见（五处需修）

1. **E9 与标签准入冲突**。2.2 定义 `CONFIRMED` 需 ≥2 强证据或 ≥1 强且总分≥3；2.3 遮蔽端规则又说 E9 成立即使光学 Type 2 仍按 CONFIRMED 处理。E9 单独只有 2 分，两条规则打架。实现前须明确 E9 是"特例直接确认"还是"降为 CANDIDATE 待补第二条"。
2. **`compute_bpt` 的 boundaries 是占位符**。4.3.7 输出写 `"kauffmann_2003":"..."`，而 4.6 示例直接消费了结果。建议写死三条分界：Kauffmann 2003 `y=0.61/(x−0.05)+1.3`；Kewley 2001 `y=0.61/(x−0.47)+1.19`；Schawinski 2007 `y=1.05x+0.45`（x=log([N II]/Hα)，y=log([O III]/Hβ)）。E2 表中"越过 Kauffmann 虚线、Kewley 实线以上"改为分区表述：线下 SF，两线间 composite，Kewley 以上 AGN/LINER。
3. **`get_spectrum` 默认线表与波长覆盖矛盾**。默认 `lines` 含 `NeV3426`（342.6 nm），output 示例覆盖 [380, 900] nm，LAMOST 拿不到这条线，E3 实际不可达。建议从默认线表移除，或在入参做波长覆盖校验并返回 `unobservable_lines`。
4. **`classify_agn` 的 evidence item 缺溯源字段**。`resolve_object` 有 `references` 与 `classification_has_spectral_ref`，但 evidence item 只有 `id/value/source`。建议加可选 `refcode` 与 `spectral_ref`，否则 A2 的"以有光谱引用者为准"无法在合成层执行。
5. **选择函数无法落地**。主文档要求"选择函数不可跳过"，但 `classify_agn` 入参没有星表流量限/覆盖/红移范围，`query_catalog` 的 `selection_function` 不会自动传过来。建议入参加 `catalog_selection_functions`（本文第 2 节已按此写）。另需明确"BPT SF 区一票否决"是否对 E9 硬 X 证据豁免：Compton-thick 的光学光谱常只看到宿主恒星形成，若被否决会系统性漏掉遮蔽端。

## 6. 风险与代价

1. NED 有 11 亿天体但仅 50.2 万条详细分类，缺分类是常态；`INDETERMINATE` 是诚实出口，不能写 `LIKELY_NON_AGN` 了事。
2. 文献分类多来自 RC3 与光谱文献，"尚未逐条附文献码"（NED Database Guide 原文）；`refcode=null` 必须保留。
3. 谱线孔径混用与 NED Homogenized Flag 低可信度，都要下调权重而非照单全收。
4. 核区偏移判定要联合 NED 基准位置的 95% 误差椭圆与警报位置误差，不能只看点估计。
5. TNS 公开归档约一天一刷，新警报当下查不到属正常，`sources_failed` 不得解读为"不是 AGN"。
6. `submit_too` 是对外写操作，须保留人工确认闸门；本用例不自动提交。
