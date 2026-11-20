# 时域天文学 MCP 服务与 NED 对接方案

- 日期：2026-11-19
- 背景：面向时域天文学的 MCP 服务构建与协同观测应用研究
- 与 `NED数据与API盘点.md` 的关系：那份是 NED 事实盘点，这份是把它接入时域项目的设计草案

## 0. 结论

1. NED 不是警报源。它一年更新 3–4 次，2026-09 单次 ingest 22 万条源属于批量入库，不具备秒级/分钟级警报能力。它在项目里的位置是**警报之后的宿主星系与静态属性富化层**。
2. 通用天文数据库 MCP 已有可复用轮子，不要重造：`aqc-mcp`（Node，17 库）、`astroquery-mcp-server`（Python，astroquery-cli 包装）、NASA-IMPACT FastMCP 自省服务（141 函数）。时域专用的 `AstroMCP` 已覆盖 TNS / ZTF / Rubin / SIMBAD / VSX / Gaia / SkyBoT。
3. 真正需要自己写的薄层只有四块：GCN Kafka 常驻监听、多源事件规范化与去重、候选排序、观测调度与人确认闸门。
4. **关键架构约束**：MCP 是请求—响应协议，GCN 是 Kafka 流。监听循环必须放在 MCP server 之外作为独立常驻进程，把结果写进事件库；MCP 只暴露对事件库的查询和调度工具。把 `consumer.consume()` 直接包进 MCP tool 会导致连接管理、背压和超时全部失控。

## 1. 分层架构

| 层 | 内容 | 自建 / 复用 |
|---|---|---|
| L1 警报接入 | GCN Kafka（`igwn.gwalert`、Fermi/Swift/SVOM/EP 等 topic）、TNS、Rubin/Fink、ZTF/ALeRCE | 自建 listener；协议与 schema 用官方库 |
| L2 规范化与去重 | 统一 JSON 事件模型、trigger ID 更新判定、ICRS 坐标与 UTC 时间归一、事件库 | 自建；参考 Astro-COLIBRI 的双库设计 |
| L3 上下文富化 | NED（GWF、NED-LVS、19 个 API）、SIMBAD、Gaia、ADS、VSX | 复用现成 MCP |
| L4 排序与调度 | 宿主概率排序、可观测性、tiling、望远镜队列、GCN Circular 回流 | 半自建；GWF 与 tilepy 可复用 |

参考架构：Astro-COLIBRI 用 Flask REST API（AWS）+ Listener（GCN Kafka / TNS / VOEvent）+ 外部 API 富化 + MongoDB（事件历史与 cone search）+ Firebase（低延迟推送）+ web/mobile 客户端，并用 tilepy 做弱定位事件的 tiling 与调度。这套结构可以直接照搬，把它的外部 API 富化层换成 MCP 工具调用。

## 2. 现成 MCP 组件盘点

| 组件 | 形态 | 覆盖 | 启动方式 | 备注 |
|---|---|---|---|---|
| `aqc-mcp` | Node.js / TypeScript，无 Python 依赖 | 17 个库 30+ 工具，含 NED、SIMBAD、Gaia、VizieR、ADS、MAST、HEASARC、IRSA、ALMA、Fermi、SDSS | `npx -y aqc-mcp`；支持 HTTP / SSE / stdio | ADS 需 `ADS_API_KEY`；直接走 TAP/REST；输出可中英 |
| `astroquery-mcp-server` | Python，包装 astroquery-cli | SIMBAD、Gaia、VizieR、MAST、NED、IRSA、ALMA | `python -m astroquery_mcp` | 有 `astroquery_ned`、`astroquery_execute`；异步+超时保护；依赖 astroquery-cli 在 PATH |
| NASA-IMPACT Astroquery MCP | Python FastMCP + 自省 | 14 模块 141 函数，NED 占 15 个 | 自建部署 | `execute(module, func, params)` 通用调用；Astropy Table 自动序列化为 JSON；适合做研究原型 |
| `AstroMCP`（PyPI 包名 `astro-checker`） | Python，只读 | 14 工具，TNS、ZTF/ALeRCE、Rubin/Fink、SIMBAD、VSX、Gaia DR3、ExoFOP、SkyBoT、图像巡天 | `astromcp` / `astro-checker` | 最贴合时域：`whats_here(ra,dec,radius)` 一次并行查所有库给出"是否已知"判定；`observe_tonight(lat,lon,...)` 给出今晚可观测的未分类 TNS 暂现源 |

以上来自第三方 MCP 目录与包仓库，未逐一验证当前版本与维护状态；正式接入前需实测接口稳定性、速率限制和结果时效性。

## 3. 警报接入的事实基线

- **GCN 新系统**以 Apache Kafka 为唯一标准协议，自助订阅、SSL/TLS、集群高可用。所有新 notice 类型只在新 GCN 上发布，优先 JSON 格式。
- VTP（VOEvent Transport Protocol）已于 **2026-04-06 退役**；新项目不要基于 socket/VTP 设计。
- Python 客户端：`pip install gcn-kafka` 或 conda-forge；`from gcn_kafka import Consumer`，用 `client_id` / `client_secret` 认证；`consumer.subscribe([...])` 后循环 `consume(timeout=1)`。
- IGWN 引力波警报走 `igwn.gwalert` topic。
- TNS 公开归档约**每天刷新一次**，不适合当作实时流；做实时发现判定必须配合 ZTF/Rubin 等 broker。
- 新 notice 的 JSON schema 统一在 `github.com/nasa-gcn/gcn-schema`，核心字段拆成 `AlertInfo` / `Identifiers` / `EventInfo` 等 building block，可作为你统一事件模型的起点。

## 4. NED 在项目中的具体用途

| 场景 | NED 入口 | 输出 |
|---|---|---|
| GW 事件宿主候选排序 | NED-GWF，事件页或 `NED::GWFglist/fits/<event>/<seq>` | 90% 概率体内全部星系 + 按 P_3D×P_LumW1 / P_SFR / P_Mstar / P_sSFR 排序；概率轮廓全天图 |
| 近邻宿主样本 | NED-LVS（约 210 万天体，D<1 Gpc，2025-06 版） | 全表下载，含 GALEX/2MASS/AllWISE 测光导出的 SFR 与恒星质量 |
| 暂现源位置宿主的静态属性 | `ConeSearchByPosition` + `OverviewOfObject` | 红移、星系类型、基准位置、直径、消光、距离 |
| 交叉证认与"是否已知" | `CrossidsOfObject`、`ReferencesOfObject`、外部链接 | NED 标准名、文献、外部资源 URL |
| SED / 谱线流量 | `PhotometryOfObject`（`SPECLINES=yes` 切谱线） | 标准化流量密度、频率、上下限、望远镜/仪器/孔径 |
| 速度参考系统一 | `VelocityConversion` | Heliocentric / GSR / Local Group / 3K 互换 |
| 银河消光改正 | `ExtinctionAtPosition` | 按波段的前景消光 |
| 文献溯源 | `ObjectsInRefcode`、ADS MCP | 19 位 bibcode 关联天体与文章 |

NED-GWF 是唯一与实时时域直接对接的 NED 服务：它自己监听 GCN，在警报后数分钟内完成 HEALPix 图与近邻星系的 3D 交叉匹配。但它是**预计算的事件级服务**，你只能按事件取结果，不能把自己的警报送进去算。

## 5. 建议的 MCP 工具集

按 MCP 三种原语划分：

**Tools（同步读，低延迟）**
- `event.get(event_id)`：从事件库取规范化事件。
- `event.cone_search(ra, dec, radius, time_range)`：本地事件库锥面+时间检索。
- `known.check(ra, dec, radius)`：并行查 TNS / SIMBAD / VSX / Gaia / NED，返回"是否已知"+证据+失败源列表（可直接复用 AstroMCP 的 `whats_here` 语义）。
- `ned.host_candidates(event_id, ranking)`：取 GWF 候选并按指定指标排序。
- `ned.object_overview(name)`、`ned.photometry(name, speclines)`：`aqc-mcp` 的 NED 工具已覆盖。
- `calc.extinction(ra, dec)`、`calc.velocity_frame(vel, ra, dec, from, to)`：包装 NED 计算器。
- `obs.observable_tonight(site, date, candidates)`：可观测性计算。
- `obs.tiling(healpix, footprint)`：tilepy 调用。

**Resources（长任务与状态）**
- `gwf://events/{event_id}/galaxies`：完整候选星系列表（可能上万行，不适合塞进 tool 返回值）。
- `job://{ticket}`：异步查询状态，对应 NED 的 Job Ticket 机制。
- `schedule://{night}`：当前观测计划。

**Prompts（把多步流程固化）**
- `gw_followup`：取警报 → 宿主排序 → 可观测性 → 生成观测计划草案 → 人工确认。
- `transient_triage`：位置查询 → 已知天体判定 → 分类 → 文献关联 → 是否上报。

## 6. 最小可行管线（MVP）

1. 起一个 GCN Kafka listener 常驻进程，只订阅 `igwn.gwalert` 和一类 GRB topic，把 notice 原始 JSON 落到 MongoDB，按 trigger ID 做更新判定。
2. 写一个 MCP server，暴露 `event.cone_search`、`known.check`、`ned.host_candidates`、`obs.observable_tonight` 四个 tool，前两个分别复用 AstroMCP 和 aqc-mcp 的后端能力。
3. 用 NED-GWF 的公开事件结果验证宿主排序链路：取一个已有事件，比对本地排序与官方 P_3D×P_LumW1 前 20。
4. 加 `obs.tiling` 和人工确认闸门，输出观测计划草案。此时"协同观测"先做到**计划协同**（共享候选表与排班），不做到自动下发指令。
5. 回流：把观测结果写回事件库，并按 NED 的数据投稿规范准备星表/测光提交材料。

先跑通这条管线再扩数据源。Rubin/LSST 正式出数后警报量级会显著上升，L2 的规范化与去重设计要提前留出扩展余量。

## 7. 风险与代价

1. **协议错配**：MCP 请求—响应模型无法承载 Kafka 流。必须拆成独立 listener + 事件库 + MCP 查询层，多一个数据库和一套状态同步逻辑，这是主要工程成本。
2. **第三方 MCP 不可控**：上述 MCP 都是社区包装，只读、无 SLA，归档可能停机或限流。AstroMCP 自己明确声明 TNS 公开归档一天一刷；关键结论必须回源确认，不能把"查不到"当成"不存在"。
3. **NED 时效性**：年更 3–4 次，新发现暂现源的宿主属性可能尚未入库；Basic Data 会修订，跨版本结果不一致。
4. **GWF 宿主先验偏差**：排序基于 GW170817（大质量早型星系 NGC 4993），用 WISE W1 光度作为恒星质量代理；BNS 宿主群体仍在争议中。排在前面的星系不等于最可能的宿主。
5. **GWF 历史数据列语义变更**：2024-05-29 修复了联合概率密度计算错误，此前的 `P_3D` 实为累积和，之后改名为 `P_3D_csum`，新的 `P_3D` 才是单位体积概率密度。用历史事件做统计必须按官方说明修正，否则排序不可比。
6. **距离完备性断崖**：NED-LVS 在 30 Mpc 内近 100% 完备，300 Mpc 约 70%，1000 Mpc 降到约 1%；若事件平均距离减 1σ 超过 1 Gpc，GWF 不做交叉匹配。大距离事件的宿主搜索要另找样本。
7. **写入操作的责任边界**：提交观测计划、发布 GCN Circular、上报 TNS 都属于对外动作，MCP 层应强制人工确认，不能由模型自动执行。多用户协同时还要处理权限与冲突排班。
8. **坐标与参考系陷阱**：不同源的坐标历元、速度参考系、测光系统不一致；统一到 ICRS / UTC / 明确带宽的流量密度后再入事件库，否则交叉匹配会出现假匹配。

## 8. 入口

- GCN：`https://gcn.nasa.gov/`；Kafka 客户端：`https://gcn.nasa.gov/docs/client`；schema：`https://github.com/nasa-gcn/gcn-schema`
- NED-GWF：`https://ned.ipac.caltech.edu/gwf/overview`；API 指南：`https://ned.ipac.caltech.edu/Documents/Guides/Interface/GWF`
- NED-LVS：`https://ned.ipac.caltech.edu/NED::LVS/`；引用 Cook et al. 2023
- Astro-COLIBRI 论文与 API 文档：`https://www.astro-colibri.science/apidoc`
- tilepy：Seglar-Arroyo et al. 2024、Schussler et al. 2026
