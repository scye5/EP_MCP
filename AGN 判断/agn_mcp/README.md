# AGN 判定 MCP 服务（agn-mcp）

面向时域天文学的 AGN 筛选判定服务，把《AGN判定_MCP服务接口设计.md》v1.0 落成可运行代码。

- 方法论：Hickox & Alexander 2018, ARA&A 56, 625
- 对齐：14 个工具、E1–E12 证据体系、五类标签、`purity`/`completeness` 双策略、选择函数强制声明
- 实测：30 项单元测试全绿；完整测试方法见 `测试指南.md`

## 目录结构

```
agn_mcp/
├── pyproject.toml
├── README.md
├── src/agn_mcp/
│   ├── __init__.py
│   ├── evidence.py     # E1–E12 唯一真值来源 + BPT 三条分界（写死，非占位符）
│   ├── criteria.py     # L2 纯函数：BPT/WHAN、WISE、X 射线、光变
│   ├── decision.py     # L3 证据合成 classify_agn 核心规则
│   ├── ned_client.py   # NED::API 客户端 + VOTable 解析（仅标准库）
│   ├── tools.py        # 14 个工具实现（纯 Python，可单测）
│   └── server.py       # FastMCP 注册层：14 tools + 5 resources + 4 prompts
├── tests/test_agn.py   # unittest 测试套件（30 项）
├── examples/
│   ├── demo_end_to_end.py      # S1 单源 A1→A9 端到端演示
│   └── demo_decision_rules.py  # 8 个规则用例，看五类标签如何触发
└── 测试指南.md          # 四层测试方法（单元/端到端/NED 联调/MCP 协议）
```

## 安装与运行

```bash
cd agn_mcp
pip install -e .              # 安装 mcp 依赖与 agn-mcp 命令
agn-mcp                       # stdio 模式（默认，供 Agent 连接）
agn-mcp --transport sse --port 8000
```

未安装 `mcp` 时，`tools` 层函数仍可直接 import 调用；仅 `create_app()` 会提示安装。
NED 调用默认走真实 API，`NED_OFFLINE=1` 可切离线模式（不发起网络请求，用于测试）。

**测试**（无需 pytest，仅标准库）：

```bash
cd agn_mcp
python -m unittest discover -s tests -v
```

## 对接口设计 v1.0 的 5 处修复（已在代码落实）

| # | 问题 | 代码中的处理 |
|---|---|---|
| 1 | E9 与标签准入冲突 | `decision.py` 步骤 4：E9 成立直接 CONFIRMED，SF 一票否决对其豁免 |
| 2 | `compute_bpt` boundaries 是占位符 | `evidence.py` 写死 Kauffmann/Kewley/Schawinski 三条分界，`compute_bpt` 输出真实公式与分区 |
| 3 | 默认线表含 NeV3426 但 LAMOST 看不到 | `tools.py` 默认线表移除 NeV3426，`get_spectrum` 返回 `unobservable_lines` 并给出覆盖提示 |
| 4 | evidence item 缺溯源字段 | evidence 项支持 `refcode` / `spectral_ref`；purity 策略下无光谱引用的分类证据拒绝升强 |
| 5 | 选择函数无法落地 | `classify_agn` 入参加 `catalog_selection_functions`，结果强制返回选择函数声明与缺失 caveat |

额外修正：BPT 的 SF/LINER 是有效测量（否决/追加规则的触发条件），不被当阴性证据丢弃；
WHAN(E4) 作为 LINER 专用追加判据可与 E2 共存但不叠加计分。

## 工具与 SOP 对应关系

| SOP | 工具链 |
|---|---|
| S1 单源 A1–A9 | `resolve_object → query_catalog → get_photometry → wise_agn_selection → query_catalog/xray_agn_selection → get_spectrum → compute_bpt → get_lightcurve/analyze_variability → classify_agn` |
| S2 批量 B1–B7 | `crossmatch → wise/xray 初筛 → find_agn_candidates`（B6 选择函数不可跳过） |
| S3 时域 C1–C6 | `get_lightcurve(EP_WXT) → crossmatch+Gaia → plan_followup/submit_too → xray_agn_selection+compute_bpt → classify_agn` |

MCP Prompts 已内置四个 SOP 编排模板：`sop_single_object`、`sop_batch_search`、
`sop_time_domain`、`sop_followup`。Resources 内置证据表、决策规则、核心文献、
星表清单、EP 仪器参数五个只读知识资源。

## 边界与注意

- **NED 是富化层，不是警报源**：3–4 次/年更新，回答"是不是已知 AGN"，不回答"本次增亮是不是 AGN 耀发"。后者属 S3，靠 E11/E12，输出写独立字段。
- **遮蔽端**：E5（WISE 颜色）分不出遮蔽与否（论文 p.18）；Compton-thick 内禀 27±4% 而 BAT 观测仅 8%（p.23），缺硬 X 必须在 caveats 声明遮蔽端不完备。
- **人工确认闸门**：`submit_too` 默认返回 `pending_human_confirmation`，不自动对外提交。
- **数据接入**：`ned_client.py` 已实现 NED::API 的 VOTable 解析；EP/ZTF/eRASS 光变与部分星表命中为外部连接器占位（`get_lightcurve` 明确标注 `data_source`），生产部署需接入对应连接器。
- **经典文献早于 EP**：判据引经典、仪器能力引 EP 最新标定，两者分开引用，不可混成一条。
