# Einstein Probe 候选体的 X 射线档案库

在 `xray_archive` 目录下运行这些 Python 3.10+ 客户端。它们接受以十进制度表示的候选体坐标。

| 脚本 | 用途 |
|---|---|
| `rosat.py` | 搜索 ROSAT 巡天源和指向观测，发现图像，并下载档案数据产品。 |
| `erosita.py` | 搜索发布目录和天区瓦片，获取位置限制，并下载 DR1 产品。 |
| `hiligt.py` | 为选定的 X 射线任务检索历史探测结果和上限。 |

```bash
python rosat.py --help
python erosita.py --help
python hiligt.py query 15.234 5.678 --mission RosatSurvey
python -m unittest -v
```

关于覆盖范围，请参阅 [数据清单](data_inventory-cn.md)；关于查询参数、下载和解读，请参阅 [服务说明](data_service-cn.md)。命令行客户端仅使用标准库。要通过 MCP 暴露 `query_survey` 和 `query_hiligt`，请安装 `python -m pip install "mcp>=1,<2"`，并使用该 Python 可执行文件以及 `archive.py` 的绝对路径来配置一个 stdio 服务器。
