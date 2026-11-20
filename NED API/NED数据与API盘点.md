# NED 数据与 API 盘点

- 盘点日期：2026-11-19
- 数据库版本：release 36.2.1（2026-09 快照）
- API 文档版本：Last Change 2026-07-09
- 来源：`ned api.pdf`（与官网 `https://ned.ipac.caltech.edu/Docs::API/` 提供的文档逐字节一致，103,568 字节，非已弃用的 legacy API）+ NED 官网 Holdings / CurrentHoldings / Release Notes / Database Guide 页面

## 0. 结论摘要

NED（NASA/IPAC Extragalactic Database）的数据分两层：

1. **库内存量**：约 11.08 亿个不同天体、139.6 亿个测光数据点、1920 万条红移、140,462 篇参考文献。
2. **API 可取数据面**：19 个 REST 服务，覆盖总览、锥面搜索、单天体逐项取数、计算工具四类，统一返回 IVOA VOTable 1.5。

NED 以河外天体为主。银河系内天体应查 SIMBAD，太阳系天体查 NASA PDS。

## 1. 库内存量（release 36.2.1）

| 数据类 | 数量 |
|---|---:|
| 不同天体（distinct objects） | 1,108,193,131 |
| 多波段交叉证认（cross-IDs） | 1,526,918,300 |
| 测光数据点（photometric data points） | 13,959,413,652 |
| 直径测量（diameters） | 609,019,857 |
| 红移测量（redshifts） | 19,196,033 |
| 有红移的天体 | 11,315,289 |
| 不依赖红移的距离（redshift-independent distances） | 252,954 |
| 有此类距离的天体 | 152,723 |
| 详细分类（detailed classifications） | 502,105 |
| 有详细分类的天体 | 229,792 |
| 详细对象备注 | 76,185 |
| 图像 | 2,653,664 |
| 光谱 | 1,818,259 |
| 独立参考文献 | 140,462 |
| 对象—文献关联 | 1,581,174,906 |

### 1.1 2026 年 9 月更新

- 从 1,065 篇文献吸收 220,722 条源。
- 新增红移 181,253 条，新增有红移天体 89,119 个。
- 新增 NED 天体 63,464 个（星系、类星体、星系团、超新星等）。
- 157,258 条文献源与已有 NED 天体交叉证认；820 条来自 Transient Name Server 的超新星（截至 2026-08）。
- 典型来源：SDSS DR18 Green Peas 9,751 条；DESI DR1 强引力透镜对 4,612 条；VIPERS 光谱红移 91,507 条。

### 1.2 特色子集

- **NED-LVS**（Local Volume Sample）：约 200 万天体，距离 < 1000 Mpc（Cook et al. 2023）。相对 NIR 光度函数的完备性：D < 30 Mpc 近 100%，300 Mpc 约 70%；亮于 L* 的星系到 400 Mpc 近 100%；到 1000 Mpc 降至约 1%。低完备性区域可见巡天足迹的人为结构，做大尺度结构/环境分析需谨慎。
- **已专门处理的大型数据集**：DESI EDR、Chandra Source Catalog 2.0.1、AllWISE、2MASS PSC、Spitzer Source List、SDSS DR13 光谱、SDSS DR6、IRAS PSC/FSC、GALEX GASC/GMSC。

## 2. API 服务总览（19 个）

| 分组 | 数量 | 服务 |
|---|---:|---|
| 总览与检索 | 5 | `OverviewOfObject`、`ConeSearchByTarget`、`ConeSearchByPosition`、`ConeSearchByIAUstyle`、`ObjectsInRefcode` |
| 单天体逐项取数 | 11 | `CrossidsOfObject`、`PositionsOfObject`、`RedshiftsOfObject`、`DistancesOfObject`、`ClassificationsOfObject`、`ExtinctionAtTarget`、`NotesOfObject`、`DiametersOfObject`、`PhotometryOfObject`、`ReferencesOfObject`、`ExternalLinksOfObject` |
| 计算工具 | 3 | `ExtinctionsAtPosition`、`CoordinateConversion`、`VelocityConversion` |

统一调用形式：`https://ned.ipac.caltech.edu/NED::API/<ServiceName>?<params>`
返回格式：IVOA VOTable 1.5（XML），含查询详情、结果元数据、数据三部分。

## 3. 各服务详解

### 3.1 OverviewOfObject

- 用途：单个天体的概览数据（旧称 byname）。
- 必填：`TARGET`（天体名，如 `NGC 0451`、`M31`）。
- 可选：`HCONST`、`OMEGAM`、`OMEGAV`（默认 67.8 / 0.308 / 0.692）。
- 示例：`https://ned.ipac.caltech.edu/NED::API/OverviewOfObject?TARGET=m31`
- 输出字段分组：
  - 基准位置：赤经赤纬（六十进制度与两种表示）、银经银纬、95% 置信误差椭圆长轴/短轴/位置角、位置文献码。
  - 基准红移与派生量：日心红移及其误差、日心视向速度及误差、红移文献码、3K CMB 参考系速度及误差、哈勃流距离及误差、平均距离与标准误。
  - 交叉证认：NED 标准格式的名字子集。
  - 分类：Object Type（G、Gpair、GTrpl、GGroup、QSO、AbLS 等）、EM 波段、物理类型、光学形态及文献码、活动类型及文献码、其他信息。
  - 快速直径：波段、长轴（2a）、文献码、物理长轴（kpc）。
  - 银河消光：Landolt V 与 UKIRT K 波段前景消光。
  - 脚注：该天体用于计算派生量的距离说明，逐个天体不同。

### 3.2 ConeSearchByTarget

- 用途：以天体名为中心的锥面搜索。
- 必填：`TARGET`。
- 可选：`MAXREC`、`RADIUS`（单位 arcmin，默认 1；`RADIUS=0` 只返回命名目标本身）、红移约束四参数。
- 输出字段：`No.`、Object Name、RA/Dec（六十进制与度）、Redshift (z)、cz、z flag、Phys Type、EM Region、Separation（角距，arcmin）、Reference/Note/Photometry/Position/Redshift/Diameter/Distances/Classification/Images/Spectra 各类记录数。

### 3.3 ConeSearchByPosition

- 用途：以坐标为中心的锥面搜索；`RA`/`Dec`、`SR` 是 IVOA Simple Cone Search 的等价键。
- 必填：`LON`、`LAT`（或 `RA`、`DEC`）。支持十进制度（`15.54d`）、小时单位（`1.036h`，仅赤道坐标）、六十进制（`01h02m10.23s` / `44d19m12s`）。
- 可选：`MAXREC`、`RADIUS`/`SR`（必须 > 0）、`CSYS`（Equatorial / Ecliptic / Galactic / SuperGalactic，默认 Equatorial）、`EQUINOX`（J2000.0 / B1950.0，赤道或黄道坐标时必填，默认 J2000.0）、红移约束。
- 示例：`https://ned.ipac.caltech.edu/NED::API/ConeSearchByPosition?LON=10.684793d&LAT=41.269065&CSYS=Equatorial&EQUINOX=J2000.0&RADIUS=1&MAXREC=2`
- 输出字段：同 `ConeSearchByTarget`。

### 3.4 ConeSearchByIAUstyle

- 用途：按 IAU 风格名称在赤道坐标系中搜索，搜索半径和中心由输入字符串的精度推算。
- 必填：`IAU_NAME`。支持格式：`HHh+DD`（096+69）、`HHMM+DD`（0955+69）、`HHMM+DDd`（0955+696）、`HHMMm+DDd`（09558+696）、`HHMMm+DDMM`（09558+6940）、`HHMMSS+DDMMm`（095552+69407）。
- 可选：`MAXREC`、`EQUINOX`（默认 B1950）、红移约束。
- 输出字段：同 `ConeSearchByTarget`。

### 3.5 ObjectsInRefcode

- 用途：按文献码（19 位 bibcode）取该文献涉及的天体。
- 必填：`REFCODE` / `BIBCODE`，如 `1997A&A...323...31K`。
- 可选：`MAXREC`；未指定时返回上限 100,000 条（结果会被截断）。
- 示例：`https://ned.ipac.caltech.edu/NED::API/ObjectsInRefcode?refcode=2024ApJ...964..117S&MAXREC=2`
- 输出字段：同 `ConeSearchByTarget`，但无 `Separation`。

### 3.6 按天体名逐项取数（11 个服务）

共用参数：`TARGET`（必填）、`MAXREC`（可选）。`PhotometryOfObject` 额外支持 `SPECLINES`：`no`（默认，连续谱测光）/ `yes`（谱线流量）。

| 服务 | 输出字段 |
|---|---|
| `CrossidsOfObject` | No.、Object Name（NED 标准格式）、Physical Type、EM Region |
| `PositionsOfObject` | RA/Dec（六十进制与度）、95% 误差椭圆长轴/短轴/位置角、文献码、Fiducial 标记 |
| `RedshiftsOfObject` | z 及误差、cz 及误差、Technique、Method、Quality Flag（? 表示不确定）、Bandpass、文献码、Fiducial 标记 |
| `DistancesOfObject` | (m−M) 及误差、距离（Mpc）、测距方法、文献码、备注、SN 名、用于换算的红移、采用的 H0（否则 70.0 km/s/Mpc）与 LMC 距离模数（否则 18.50） |
| `ClassificationsOfObject` | 分类域（Galaxy Morphology / Radio Morphology / Distance Indicator / Kinematics / Activity Type / Luminosity Class / Hierarchy）、发表分类、文献码、NED 归一化分类及 flag、波段、适用空间区域、备注 |
| `ExtinctionAtTarget` | 波段、加权中心波长（μm）、银河前景消光（mag）、文献码 |
| `NotesOfObject` | 文献码、Object Name、备注文本（转录自源目录或论文） |
| `DiametersOfObject` | 波段、长轴/短轴及误差、长轴位置角及误差、轴比 b/a、直径类型（等光度、半光、FWHM 等）、参考面亮度、文献码、注释 |
| `PhotometryOfObject` | 波段、原始测量值、谱线类型（发射/吸收/both）、上下误差、原始单位；标准化后的频率（Hz）、流量密度（Jy）、FD 上下误差与上下限、流量（Jy·Hz）及上下误差与上下限；望远镜、仪器、频率与单位、孔径类型、文献码 |
| `ReferencesOfObject` | 文献码、作者列表、文章标题 |
| `ExternalLinksOfObject` | 资源标签、外部资源 URL |

### 3.7 红移约束参数（适用于三个 ConeSearch 服务）

| 参数 | 说明 |
|---|---|
| `Z_CONSTRAINT` | `Unconstrained`（默认）/ `Available` / `Unavailable` / `LargerThan` / `LessThan` / `Between` |
| `Z_VALUE1` | `LargerThan`、`LessThan` 的边界；`Between` 的下界 |
| `Z_VALUE2` | `Between` 的上界，不小于 `Z_VALUE1` |
| `Z_UNIT` | `z`（默认）或 `km/s` |

示例：`...&z_constraint=Between&z_value1=4.2&z_value2=96&RADIUS=1.0&z_unit=km/s`

### 3.8 ExtinctionsAtPosition

- 用途：查询任意坐标处的银河前景消光。注意：PDF 服务标题写作 `ExtinctionsAtPosition`，但示例 URL 使用 `ExtinctionAtPosition`，文档自身不一致，调用时两者都应试。
- 必填：`LON`、`LAT`。
- 可选：`MAXREC`、`CSYS`（默认 Galactic）、`EQUINOX`（赤道/黄道坐标时必填）、`EPOCH`（未给出时按 EQUINOX 取 2000.0 / 1950.0，否则取 1950）。
- 输出字段：同 `ExtinctionAtTarget`。

### 3.9 CoordinateConversion

- 用途：坐标系转换。
- 必填：`LON`、`LAT`、`OUT_CSYS`。
- 可选：`IN_CSYS`（默认 Equatorial）、`IN_EQUINOX`、`OBS_EPOCH`、`PA`（默认 0.0）、`OUT_EQUINOX`。
- 支持坐标系：Equatorial / Galactic / SuperGalactic / Ecliptic；分点 J2000.0 / B1950.0。
- 输出字段：输入与输出的系统、分点、观测历元、经纬度（度与六十进制）、位置角。

### 3.10 VelocityConversion

- 用途：不同参考系间的视向速度（红移）换算。
- 必填：`LON`、`LAT`、`VEL`（km/s）。
- 可选：`IN_CSYS`（默认 Equatorial）、`IN_EQUINOX`（默认 J2000.0）、`VFROM`（Heliocentric / GSR / Local Group / 3K，默认 Heliocentric）、`VTO`（同选项，默认 GSR）、`USER_DEFINED`（no/yes）、自定义 apex 的 `A_CSYS`、`A_EQUINOX`、`ALON`、`ALAT`、`AVEL`。
- 输出字段：输入/输出系统、分点、坐标、速度、参考系、apex 向量、输出速度。

## 4. 调用约定与风险

1. `MAXREC=0` 只返回字段定义，不返回数据；不指定 `MAXREC` 则全量返回或受服务资源限额约束（`ObjectsInRefcode` 上限 100,000）。
2. 锥面搜索默认半径 1 arcmin。`ByTarget` 允许 `RADIUS=0`（只返回目标本身）；`ByPosition` 的 `RADIUS`/`SR` 必须 > 0。
3. 取谱线流量必须给 `PhotometryOfObject` 加 `SPECLINES=yes`，默认只返回连续谱测光。
4. 距离要分清来源：1,920 万条红移大多用于算哈勃流距离，依赖所选宇宙学参数；真正红移无关的距离仅 25.3 万条、覆盖 15.3 万天体。混用会引入系统偏差。
5. 红移质量需看 `z flag`：技术 1 位（如 S=光谱、P=测光）、方法 2 位（如 SL=单线）、质量 1 位（空白=可靠、?=不确定）。
6. NED 以 1988 年后的主要同行评议期刊为主要覆盖源；预印本、会议集、学位论文、天文台专刊可能缺失。
7. 官网已声明 legacy API 弃用，新接入使用本文的 `NED::API` 路径。另有 2026 年 5 月上线的基于 IVOA TAP 的参数检索入口（支持 ADQL），PDF 未收录；做批量筛选时可单独查阅。
8. 数据版本按年 3–4 次发布；Basic Data 会不断修订，同一查询跨版本结果可能变化。

## 5. 网站交互功能（区别于 API）

### 5.1 检索入口

| 入口 | 能力 | 关键限制 |
|---|---|---|
| By Name | 名称解释器容错：`n33`→`NGC 0033`、`M81`→`MESSIER 081`、`mk1000`→`MRK 1000` 等；歧义名给候选列表；可设宇宙学模型（Planck 2015 / WMAP 各期 / 自定义）与红移参考系（3K CMB、仅 Virgo infall、Virgo+Great Attractor、Virgo+GA+Shapley） | 能识别命名法不等于对象已收录 |
| Near Name / Near Position / IAU Search | 锥面搜索；半径默认 1 arcmin，最大 60 arcmin；支持赤道/黄道/银道/超银道、J2000/B1950；IAU 搜索默认 B1950 | 单次最多返回 50,000 个对象；密集天区大半径会很慢 |
| By Parameters | 全天多条件：天区 Box/Cone、RA/Dec 与银经银纬区间（后者支持 Not Between）、红移（z 或 km/s）、流量密度或星等的 Bright/Faint/Between/Not Between、对象类型（Union=OR，Intersection=AND）、名称前缀、测光/直径/红移无关距离数据点数下限、宇宙学、输出坐标、排序、格式 | 走队列调度，需凭 Job Ticket 取结果 |
| By Refcode | 19 位 bibcode 取文献中的天体 | 大小写敏感；只覆盖期刊论文，不含目录/图书/学位论文；页面最多显示 1,000 条，1,000–100,000 条可下载，>100,000 需联系 helpdesk |
| By Classification / Types / Attributes | 七类约束：Galaxy Morphology、Radio Morphology、Distance Indicator、Activity Type、Luminosity Class、Kinematics、Hierarchy；可选 NED Homogenized 与误差、轴比、位置角等详细字段 | 经典 UI，正在移植；分类数据并非全覆盖 |
| By Input List | Object Name Matches（名称批量匹配）、Positional Cross-Matches（位置交叉匹配） | 经典 UI，正在移植；文档未展开细节 |
| By Environment | 按环境检索对象 | 经典 UI，正在移植 |
| Literature | References by Author Name、Reference Lookup、Nomenclature（缩写与定义） | — |

### 5.2 天体详情页

一个对象的页面集中展示：概览（基准位置、红移、派生距离、类型、直径、消光）、Cross-IDs、坐标、红移、测光与 SED、光谱、图像、直径、红移无关距离、分类、备注、参考文献、外部链接。图像和光谱可下载 FITS。

### 5.3 在线计算器

- Coordinate Calculator：赤道/银道/超银道/黄道互换，含 J2000/B1950 与观测历元、位置角。
- Extinction Calculator：给定位置按波段算银河前景消光。
- Velocity Calculator：Heliocentric / GSR / Local Group / 3K 参考系间换算，支持自定义 apex。

### 5.4 特色服务

- **Gravitational Wave Followup (GWF)**：监听 GCN 上 LIGO/Virgo/KAGRA 警报，数分钟内把事件的 HEALPix 概率图与 NED 近邻星系做 3D 交叉匹配。输出：概率轮廓全天图、90% 概率体积内全部星系、按 P_3D×P_LumW1 排序的前 20 个候选星系；完整列表还可按 P_3D×P_SFR、P_3D×P_Mstar、P_3D×P_sSFR 排序下载。样本为 NED-LVS，距离上限 1 Gpc（2020-01 前为 200 Mpc）。有专用 API，例如 `https://ned.ipac.caltech.edu/uri/NED::GWFglist/fits/S200129m/2`。引用 DOI: 10.26132/NED3。
- **NED-LVS**：约 210 万天体（2025-06 版），提供全表下载。
- **Ticket Status**：长查询结果取回。
- **Level5**：河外天文与宇宙学知识库及术语表。
- **Classic Home Page**：旧界面入口，部分功能尚未移植。

### 5.5 输出格式与批量

VOTable BINARY2 / TABLEDATA（.vot）、CSV、TSV、竖线分隔文本、JSON；可按 RA、Dec、银经、银纬、红移（升降序）排序。大型全天检索通过 NBASQ 队列调度，状态 Accepted / Queued / Running / Complete，约每 10 秒刷新；超过一小时的建议联系 NED 申请 special token。用户可向 NED 提交星表、FITS 图像和光谱。

## 6. 实用入口

- 主页与单行搜索：`https://ned.ipac.caltech.edu/`
- 按名称：`/byname`；锥面搜索：`/conesearch`；按文献码：`/inrefcode`；按参数全天：`/byparams`
- 文献检索：`/refbyauthor`、`/reflookup`；命名法：`/srcnom`
- 三个计算器：`/coordinate_calculator`、`/extinction_calculator`、`/velocity_calculator`
- 引力波跟进：`/gwf/overview`、`/gwf/events`；Ticket 状态：`/ticket_monitor`
- 检索指南：`https://ned.ipac.caltech.edu/Documents/Guides/Searches`
- 库内统计：`https://ned.ipac.caltech.edu/CurrentHoldings`
- 数据存量说明：`https://ned.ipac.caltech.edu/Documents/Holdings`
- 大型数据集：`https://ned.ipac.caltech.edu/Documents/Holdings/Sets`
- 发布记录：`https://ned.ipac.caltech.edu/Documents/Overview/Release`
- 数据库常见问题（对象类型码、星等体系、图像说明等）：`https://ned.ipac.caltech.edu/Documents/Guides/Database`
- NED-LVS：`https://ned.ipac.caltech.edu/NED::LVS/`
