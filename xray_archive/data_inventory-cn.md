# 面向 EP 候选体的 ROSAT 与 eROSITA 数据清单

审阅日期：2026 年 11 月 22 日。首先从 EP 候选体的位置、定位半径和观测日期入手。目录用于回答“附近探测到了哪些源”。当目录中没有匹配项时，历史观测也可以对候选体加以约束。

| 数据集合 | 提供的内容 | 它如何为 EP 候选体提供信息 |
|---|---|---|
| ROSAT 全天巡天 (RASS) | RASSMASTER 中的 PSPC 巡天扫描和已处理的巡天场。2RXS 目录包含约 135,000 个在 0.1–2.4 keV 波段内的探测结果，提供位置、计数率、硬度比、质量标志，以及在可获取情况下的能谱或光变测量。较旧的亮源和暗源目录使用的是早期处理流程。 | 在 2RXS 中搜索历史源。在密集或弥散区域检查质量标志。目录计数率在与 EP 能量通量比较之前，需要先做能谱假设。[2RXS 目录](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A+A/588/A103) · [RASSMASTER](https://heasarc.gsfc.nasa.gov/W3Browse/rosat/rasspublic.html) |
| ROSAT 指向观测 | ROSMASTER 按位置、时间、仪器和曝光对 PSPC 与 HRI 观测建立索引。公开的已处理数据集可能包含事件列表、图像、背景、附属文件和处理摘要。可用性因仪器和序列而异。 | 指向观测的曝光可以约束已知源列表之外的位置。应结合实际的视场和曝光图来核查候选体。档案坐标通常描述的是指向中心。[ROSMASTER](https://heasarc.gsfc.nasa.gov/W3Browse/rosat/rospublic.html) · [HEASARC 档案布局](https://heasarc.gsfc.nasa.gov/docs/rosat/archive_access.html) |
| eROSITA-DE 早期数据发布 | 定标和性能验证场，包括 eFEDS。这些定向观测和类巡天观测各自拥有独立的覆盖范围和发布产品。 | 当在这些场之一中研究候选体时，应单独检查其覆盖重叠情况。[早期数据发布](https://erosita.mpe.mpg.de/edr/) |
| eROSITA-DE DR1 (eRASS1) | 首次巡天扫描，2019 年 12 月至 2020 年 6 月。包含主目录、补充目录、硬波段目录和星系团目录。德国发布包含 2,447 个相互重叠的瓦片，其中包括部分覆盖的边界瓦片。产品包括定标后的事件、图像、曝光图和背景图、灵敏度图、面积曲线，以及选定的源产品，如能谱和光变曲线。 | 使用主目录作为 0.2–2.3 keV 基线，硬波段目录用于 2.3–5 keV，并使用地图或上限服务来核查特定位置。曝光在瓦片之间以及瓦片内部都有差异。[DR1 产品](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/) · [目录接口](https://erosita.mpe.mpg.de/erodat/apis/) |
| eROSITA-DE DR2 (eRASS:3) | 三次扫描合并后的主目录和硬波段目录（2019 年 12 月至 2021 年 6 月），外加位置上限。公开发布覆盖西银道半球。瓦片事件列表、图像、曝光图和源光变曲线可通过 DR1 在其对应历元获取。 | 使用 DR2 进行更深度的历史对应源搜索。其累积通量可能稀释一次短促的耀发。DR1 和 DR2 共享首次扫描，因此它们的测量结果在统计上相互依赖。[DR2 范围与日期](https://erosita.mpe.mpg.de/dr2/AllSkySurveyData_dr2/) |
| eROSITA 位置上限 | 按波段划分的孔径测光，附带曝光、通量上限和覆盖元数据。DR1 提供五个能段，DR2 提供两个。DR1 的上限 FITS 表也可按瓦片下载。 | 首先检查覆盖范围和曝光。在 DR1 中，`UL_B` 使用无源背景。在靠近目录探测到的源时，`UL_S` 会将该源的 PSF 模型纳入背景，从而约束一个假设的额外源。[上限定义](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/UpperLimitServer_dr1/) |

对于候选体报告，应保留目录/发布版本或观测 ID、角距离、观测日期、能段、通量或计数率单位、不确定度或上限置信度、曝光和能谱假设。一个 EP 定位范围内可能落入多个天体。档案匹配为后续跟踪观测提供依据；耀发或活动星系核 (AGN) 的分类则需要源证认以及相符的亮度或能谱测量。
