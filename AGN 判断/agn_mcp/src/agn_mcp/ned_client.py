"""NED::API 数据接入客户端（仅用标准库）。

统一调用：https://ned.ipac.caltech.edu/NED::API/<Service>?<params>
返回 IVOA VOTable 1.5（XML）。本模块负责取回并解析为 list[dict]，
供 L1 工具消费。支持离线模式（NED_OFFLINE=1）以便无网络测试。

注意（盘点文档第 4 节）：
  - PhotometryOfObject 需 SPECLINES=yes 才返回谱线流量；
  - MAXREC=0 只返回字段定义；
  - ConeSearchByPosition 的 RADIUS/SR 必须 > 0，ByTarget 允许 0；
  - ExtinctionsAtPosition / ExtinctionAtPosition 两种拼写都试。
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

NED_BASE = "https://ned.ipac.caltech.edu/NED::API"
DEFAULT_TIMEOUT = float(os.environ.get("NED_TIMEOUT", "30"))
NED_OFFLINE = os.environ.get("NED_OFFLINE", "0") == "1"


@dataclass
class VotableResult:
    service: str
    url: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    raw_bytes: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "n_rows": len(self.rows),
            "fields": [f["name"] for f in self.fields],
            "rows": self.rows,
            "error": self.error,
        }


def ned_query(service: str, params: dict[str, Any], timeout: float | None = None) -> VotableResult:
    """调用一个 NED 服务并解析 VOTable。失败时返回带 error 的结果，不抛异常。"""
    params = {k: v for k, v in params.items() if v is not None}
    url = f"{NED_BASE}/{service}?{urllib.parse.urlencode(params)}"
    result = VotableResult(service=service, url=url)

    if NED_OFFLINE:
        result.error = "NED_OFFLINE=1：离线模式，未发起网络请求"
        return result

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agn-mcp/0.1 (time-domain AGN pipeline)"})
        with urllib.request.urlopen(req, timeout=timeout or DEFAULT_TIMEOUT) as resp:
            payload = resp.read()
        result.raw_bytes = len(payload)
        result.fields, result.rows = parse_votable(payload)
    except Exception as exc:  # noqa: BLE001 - 网络错误统一降级为结果对象
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def parse_votable(payload: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """解析 VOTable 1.5 的第一个 TABLE（TABLEDATA 与 BINARY2 的 TABLEDATA 回退）。

    返回 (fields, rows)，字段名以 FIELD 的 name 属性为准，NULL 单元格置 None。
    """
    root = ET.fromstring(payload)
    tables = root.findall(".//TABLE")
    if not tables:
        return [], []
    table = tables[0]

    fields: list[dict[str, Any]] = []
    for f in table.findall("FIELD"):
        fields.append({
            "name": f.get("name", ""),
            "ucd": f.get("ucd", ""),
            "unit": f.get("unit", ""),
            "datatype": f.get("datatype", ""),
        })

    names = [f["name"] for f in fields]
    rows: list[dict[str, Any]] = []
    tabledata = table.find(".//TABLEDATA")
    if tabledata is None:
        return fields, rows
    for tr in tabledata.findall("TR"):
        cells = tr.findall("TD")
        row: dict[str, Any] = {}
        for i, td in enumerate(cells):
            name = names[i] if i < len(names) else f"col_{i}"
            if name in row:  # 重复列名加后缀
                name = f"{name}_{i}"
            row[name] = None if td.get("null") == "1" or td.text is None else td.text.strip()
        rows.append(row)
    return fields, rows


def pick(row: dict[str, Any], *candidates: str, default: Any = None) -> Any:
    """按候选字段名（大小写/关键子串匹配）从一行里取值。"""
    lowered = {str(k).lower(): v for k, v in row.items()}
    for cand in candidates:
        key = cand.lower()
        if key in lowered:
            return lowered[key]
        for k, v in lowered.items():
            if key in k or k in key:
                return v
    return default


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def coord_to_ned(lon: float, lat: float) -> tuple[str, str]:
    """十进制度 -> NED 接受的 LON/LAT 字符串。"""
    return f"{lon:.6f}d", f"{lat:.6f}"
