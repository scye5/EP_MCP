# 面向 EP 候选体的 ROSAT 与 eROSITA 数据清单

审阅日期 2026 年 11 月 22 日。先确定 EP 候选体的位置、定位半径与观测日期。星表回答“附近探测到了哪些源”。当星表没有匹配项时，一次历史观测也可约束候选体。

| 数据集 | 可获得的内容 | 如何为 EP 候选体提供信息 |
|---|---|---|
| ROSAT 全天巡天（RASS） | RASSMASTER 中的 PSPC 巡天扫描与处理后的巡天视场。2RXS 星表包含约 135,000 个 0.1–2.4 keV 探测，带有位置、计数率、硬度比、质量标志，以及（在可获得时）光谱或光变测量。较早的亮源与暗源星表使用更早的处理流程。 | 在 2RXS 中搜索历史源。在拥挤或弥散区域检查质量标志。星表计数率在转换为与 EP 能通量比较前，需先做光谱假设。[2RXS 星表](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A+A/588/A103) · [RASSMASTER](https://heasarc.gsfc.nasa.gov/W3Browse/rosat/rasspublic.html) |
| ROSAT 指向观测 | ROSMASTER 按位置、时间、仪器与曝光索引 PSPC 与 HRI 观测。公开处理后的数据集可包含事件表、图像、背景、辅助文件与处理摘要。可用性因仪器与序列而异。 | 一次指向观测的曝光可约束已知源表之外的位置。将候选体与实际的视场及曝光图进行核对。档案坐标通常描述的是指向中心。[ROSMASTER](https://heasarc.gsfc.nasa.gov/W3Browse/rosat/rospublic.html) · [HEASARC 档案布局](https://heasarc.gsfc.nasa.gov/docs/rosat/archive_access.html) |
| eROSITA-DE 早期数据发布（Early Data Release） | 定标与性能验证视场，包括 eFEDS。这些定向且类巡天的观测有其自身的覆盖区与发布产品。 | 当研究这些视场之一中的候选体时，单独检查覆盖重叠情况。[早期数据发布](https://erosita.mpe.mpg.de/edr/) |
| eROSITA-DE DR1（eRASS1） | 首次巡天巡扫，2019 年 12 月至 2020 年 6 月。主星表、补充星表、硬波段星表与星系团星表。德国发布包含 2,447 个重叠天区，其中包括部分覆盖的边界天区。产品包括定标事件、图像、曝光与背景图、灵敏度图、面积曲线，以及选定的源产品（如光谱与光变曲线）。 | 主星表用于 0.2–2.3 keV 基线，硬波段星表用于 2.3–5 keV，并用地图表或上限服务检查特定位置。曝光在天区之间及天区内部均有差异。[DR1 产品](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/) · [星表接口](https://erosita.mpe.mpg.de/erodat/apis/) |
| eROSITA-DE DR2（eRASS:3） | 三次巡扫合并的主星表与硬波段星表，2019 年 12 月至 2021 年 6 月，外加位置上限。公开发布覆盖西银道半球。天区事件表、图像、曝光图与源光变曲线可通过 DR1 在其相应历元获取。 | 使用 DR2 进行更深的历史对应源搜索。其累积通量可能稀释一次短暂耀发。DR1 与 DR2 共享第一次巡扫，因此二者的测量在统计上是相关的。[DR2 范围与日期](https://erosita.mpe.mpg.de/dr2/AllSkySurveyData_dr2/) |
| eROSITA 位置上限 | 分能段的孔径测光，带曝光、通量上限与覆盖元数据。DR1 提供五个能段，DR2 提供两个。DR1 的上限 FITS 表也可按天区下载。 | 先检查覆盖区与曝光。在 DR1 中，`UL_B` 使用无源背景。在已编目探测附近，`UL_S` 将源的 PSF 模型纳入背景，从而约束一个假想的额外源。[上限定义](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/UpperLimitServer_dr1/) |

对于候选体报告，保留星表/发布或观测 ID、角距、观测日期、能段、通量或计数率单位、不确定度或上限置信度、曝光与光谱假设。一个 EP 定位内可能包含多个天体。档案匹配为后续观测提供证据；而耀发或 AGN 分类需要源证认以及兼容的亮度或光谱测量。
