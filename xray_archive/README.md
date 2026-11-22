# 爱因斯坦探针（Einstein Probe）候选体的 X 射线档案

在 `xray_archive` 目录下运行这些 Python 3.10+ 客户端。它们以十进制度为单位接收候选体坐标。

| 脚本         | 用途                                                        |
| ------------ | ----------------------------------------------------------- |
| `rosat.py`   | 搜索 ROSAT 巡天源与指向观测，发现图像，并下载档案数据产品。 |
| `erosita.py` | 搜索发布星表与天空瓦片，检索位置限制，并下载 DR1 数据产品。 |
| `hiligt.py`  | 检索指定 X 射线任务的历史探测与上限。                       |

```bash
python rosat.py --help
python erosita.py --help
python hiligt.py query 15.234 5.678 --mission RosatSurvey
python -m unittest -v
```

有关覆盖范围，请参阅[数据清单](data_inventory-cn.md)；有关查询参数、下载与结果解读，请参阅[服务说明](data_service-cn.md)。命令行客户端仅使用标准库。若要通过 MCP 暴露 `query_survey` 和 `query_hiligt`，请安装 `python -m pip install "mcp>=1,<2"`，并使用该 Python 可执行文件与 `archive.py` 的绝对路径配置一个 stdio 服务器。
