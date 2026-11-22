# X-ray archives for Einstein Probe candidates

Run these Python 3.10+ clients from `xray_archive`. They accept candidate coordinates in decimal degrees.

| Script | Use |
|---|---|
| `rosat.py` | Search ROSAT survey sources and pointings, discover images, and download archive products. |
| `erosita.py` | Search release catalogues and sky tiles, retrieve positional limits, and download DR1 products. |
| `hiligt.py` | Retrieve historical detections and upper limits for a selected X-ray mission. |

```bash
python rosat.py --help
python erosita.py --help
python hiligt.py query 15.234 5.678 --mission RosatSurvey
python -m unittest -v
```

See [data inventory](data_inventory.md) for coverage and [service instructions](data_service.md) for query parameters, downloads, and interpretation. The command-line clients use the standard library. To expose `query_survey` and `query_hiligt` over MCP, install `python -m pip install "mcp>=1,<2"` and configure a stdio server with that Python executable and the absolute path to `archive.py`.
