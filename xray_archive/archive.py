"""Position-based archival X-ray queries. Coordinates are decimal degrees."""

import json
import math
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET


VIZIER = "https://vizier.cfa.harvard.edu/viz-bin/votable"
HILIGT = "https://xmmuls.esac.esa.int/ULSnewservice_passthru"
CATALOGS = {
    "rosat": ("J/A+A/588/A103/cat2rxs", ["2RXS", "RAJ2000", "DEJ2000", "CRate", "e_CRate", "Fluxp"]),
    "erosita": ("J/A+A/682/A34/erass1-m", ["IAUName", "RA_ICRS", "DE_ICRS", "MLFlux1", "s_MLFlux1"]),
}
MISSIONS = ("XMMpnt", "XMMslew", "XMMstacked", "SwiftXRT", "NuSTAR", "RosatPointedPSPC",
            "RosatPointedHRI", "RosatSurvey", "eROSITA", "Einstein", "Asca", "Integral",
            "ExosatLE", "ExosatME", "Ginga", "Ariel5", "Heao1", "Vela5B", "Uhuru", "Sax")


def fetch(url, params):
    with urlopen(url + "?" + urlencode(params), timeout=120) as response:
        return response.read()


def position(ra, dec):
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise ValueError("Expected RA in [0, 360) and Dec in [-90, 90] degrees")


def number(value):
    if value is None or str(value).strip().lower() in {"", "null"}:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite archive measurement")
    return result


def query_survey(survey: Literal["rosat", "erosita"], ra_deg: float, dec_deg: float,
                 radius_arcsec: float = 90, limit: int = 100) -> dict:
    """Find nearby ROSAT 2RXS or eROSITA eRASS1 main sources, closest first."""
    position(ra_deg, dec_deg)
    if not 0 < radius_arcsec <= 648000 or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Expected a positive radius up to 180 degrees and limit of 1–1000")
    table, columns = CATALOGS[survey]
    params = {"-source": table, "-c": f"{ra_deg} {dec_deg:+}", "-c.rs": radius_arcsec,
              "-out": ",".join(columns), "-out.add": "_r", "-sort": "_r", "-out.max": limit + 1}
    root = ET.fromstring(fetch(VIZIER, params))
    for info in root.findall(".//{*}INFO"):
        if info.get("name", "").lower() == "error" or info.get("value", "").upper() == "ERROR":
            raise ValueError(f"VizieR error: {info.text or info.get('value')}")
    result = root.find(f".//{{*}}TABLE[@name='{table}']")
    if result is None:
        raise ValueError("Missing requested VizieR table")
    fields = [f.attrib["name"] for f in result.findall("{*}FIELD")]
    if not set(["_r", *columns]).issubset(fields):
        raise ValueError("Missing VizieR measurement columns")
    matches = []
    for row in result.findall(".//{*}TR"):
        values = dict(zip(fields, [cell.text for cell in row.findall("{*}TD")], strict=True))
        match = {"source": values[columns[0]], "ra_deg": float(values[columns[1]]),
                 "dec_deg": float(values[columns[2]]), "separation_arcsec": float(values["_r"])}
        if survey == "rosat":
            match.update(count_rate_cps=number(values["CRate"]), count_rate_error_cps=number(values["e_CRate"]),
                         absorption_corrected_pl_flux=number(values["Fluxp"]))
        else:
            match.update(flux=number(values["MLFlux1"]), flux_error=number(values["s_MLFlux1"]))
        matches.append(match)
    matches.sort(key=lambda item: item["separation_arcsec"])
    return {"catalogue": table, "band_keV": [0.1, 2.4] if survey == "rosat" else [0.2, 2.3],
            "flux_unit": "erg cm^-2 s^-1", "radius_arcsec": radius_arcsec,
            "truncated": len(matches) > limit, "matches": matches[:limit]}


def query_hiligt(ra_deg: float, dec_deg: float, mission: str = "XMMpnt",
                 sigma: int = 3, power_law_slope: float = 1.7, nh_cm2: float = 3e20,
                 blackbody_ev: int | None = None, use_catalogue: bool = True) -> dict:
    """Query one HiLIGT mission per call for observations, detections and upper limits."""
    position(ra_deg, dec_deg)
    if mission not in MISSIONS:
        raise ValueError(f"Choose one of {', '.join(MISSIONS)}")
    if sigma not in (1, 2, 3) or nh_cm2 not in (1e20, 3e20, 1e21):
        raise ValueError("Unsupported significance or absorption column")
    if power_law_slope not in (0.5, 1, 1.5, 1.7, 2, 2.5, 3, 3.5):
        raise ValueError("Unsupported HiLIGT power-law slope")
    column = {1e20: "1.0E20", 3e20: "3.0E20", 1e21: "1.0E21"}[nh_cm2]
    if blackbody_ev is not None and blackbody_ev not in (60, 100, 300, 1000):
        raise ValueError("Blackbody temperature must be 60, 100, 300 or 1000 eV")
    params = dict(mission=mission, ra=ra_deg, dec=dec_deg, label="target",
                  bands="hard" if mission == "Ariel5" else "all", FORMAT="JSON", ulsig=sigma,
                  model="plaw" if blackbody_ev is None else "bbody",
                  specparam=power_law_slope if blackbody_ev is None else blackbody_ev / 1000,
                  nh=column, usecat="yes" if use_catalogue else "no")
    rows = json.loads(fetch(HILIGT, params))
    if not isinstance(rows, list):
        raise ValueError("Expected HiLIGT observation list")
    observations = []
    for row in rows:
        status = row["_status"]
        if status == "NoDataFound":
            continue
        if status != "Ok":
            raise ValueError(f"HiLIGT {mission}: {status}")
        flux = number(row.get("_crate_flux"))
        upper = number(row.get("_ul_flux"))
        observations.append({"obsid": row["_obsid"], "instrument": row.get("_instrum"),
                             "start": row.get("_start_date"), "end": row.get("_end_date"),
                             "band_keV": [float(row["_elow"]), float(row["_ehigh"])],
                             "flux": flux, "flux_error": number(row.get("_crate_flux_err")),
                             "count_rate_cps": number(row.get("_crate")),
                             "count_rate_error_cps": number(row.get("_crate_err")),
                             "count_rate_upper_limit_cps": number(row.get("_ul")),
                             "flux_upper_limit": upper, "sigma": number(row.get("_ulsig")),
                             "exposure_s": number(row.get("_exptime"))})
    return {"query": params, "flux_unit": "erg cm^-2 s^-1", "observations": observations}


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("ep-xray-archive")
    server.tool()(query_survey)
    server.tool()(query_hiligt)
    server.run()
