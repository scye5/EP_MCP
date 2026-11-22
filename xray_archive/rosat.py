"""ROSAT observation discovery and product access through HEASARC."""
import argparse
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode, urlsplit
from archive import query_hiligt, query_survey

from archive_io import cli, coordinates, download, download_command, request, validate_position, votable, write_votable

BUCKET = "https://nasa-heasarc.s3.amazonaws.com"
TAP = "https://heasarc.gsfc.nasa.gov/xamin/vo/tap/sync"


def products(prefix):
    if not prefix.startswith("rosat/") or not prefix.endswith("/"):
        raise ValueError("Use a ROSAT prefix beginning with rosat/ and ending in /")
    params = {"list-type": 2, "prefix": prefix, "delimiter": "/"}
    while True:
        with request(BUCKET + "/", params) as stream:
            page = ET.parse(stream).getroot()
        for directory in page.findall("{*}CommonPrefixes/{*}Prefix"):
            yield {"prefix": directory.text}
        for entry in page.findall("{*}Contents"):
            key = entry.findtext("{*}Key")
            if not key.endswith("/"):
                yield {"url": BUCKET + "/" + quote(key), "bytes": int(entry.findtext("{*}Size"))}
        token = page.findtext("{*}NextContinuationToken")
        if not token:
            return
        params["continuation-token"] = token


def index_rows(url):
    with request(url) as response:
        page = response.read().decode("latin-1")
    if "Sequence ID" not in page:
        raise ValueError(f"Unexpected ROSAT archive index: {url}")
    for line in page.splitlines():
        if "</a>" not in line.lower() or "processed_data/" not in line:
            continue
        plain = unescape(re.sub(r"<[^>]*>", "", line))
        match = re.fullmatch(
            r"\s*(.*?)\s+(\S+)\s+(\S+)\s+(\d+)h\s*(\d+)m\s*([\d.]+)s\s+"
            r"([+-]?\d+)d\s*(\d+)m\s*([\d.]+)s\s+(\S+)\s+(\d+)\s*.*", plain)
        if not match:
            raise ValueError(f"Unrecognized observation in {url}: {plain[:120]}")
        name, start, end, h, m, s, d, dm, ds, sequence, exposure = match.groups()
        ra = 15 * (float(h) + float(m)/60 + float(s)/3600)
        dec = math.copysign(abs(float(d)) + float(dm)/60 + float(ds)/3600, float(d))
        yield name, ra, dec, sequence, exposure, start, end


def pointed_index(ra, dec, radius):
    root = ET.Element("VOTABLE", xmlns="http://www.ivoa.net/xml/VOTable/v1.3", version="1.3")
    resource = ET.SubElement(root, "RESOURCE", type="results")
    ET.SubElement(resource, "INFO", name="QUERY_STATUS", value="OK")
    table = ET.SubElement(resource, "TABLE", name="ROSAT pointed archive indexes")
    ET.SubElement(table, "DESCRIPTION").text = "PSPC and HRI processed-data indexes at " + BUCKET
    for name, datatype, unit in (("name","char",""), ("ra","double","deg"), ("dec","double","deg"),
                                 ("sequence_id","char",""), ("exposure","int","s"),
                                 ("start_date","char",""), ("end_date","char","")):
        field = ET.SubElement(table, "FIELD", name=name, datatype=datatype)
        if datatype == "char":
            field.set("arraysize", "*")
        if unit:
            field.set("unit", unit)
    rows = ET.SubElement(ET.SubElement(table, "DATA"), "TABLEDATA")
    urls = [f"{BUCKET}/rosat/data/{instrument}/processed_data/{group}00000.html"
            for instrument in ("pspc", "hri") for group in range(10)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for page in pool.map(lambda url: list(index_rows(url)), urls):
            for row in page:
                _, r, d, *_ = row
                hav = (math.sin(math.radians(d-dec)/2)**2 + math.cos(math.radians(d)) *
                       math.cos(math.radians(dec)) * math.sin(math.radians(r-ra)/2)**2)
                if hav <= math.sin(math.radians(radius)/2)**2 + 1e-16:
                    tr = ET.SubElement(rows, "TR")
                    for value in row:
                        ET.SubElement(tr, "TD").text = str(value)
    sys.stdout.buffer.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    adql = commands.add_parser("tap", help="Run a synchronous ADQL query and write a VOTable")
    adql.add_argument("query")
    for name in ("cone", "images"):
        service = commands.add_parser(name, help="HEASARC Simple Cone Search" if name == "cone"
                                      else "HEASARC Simple Image Access discovery")
        coordinates(service)
        service.add_argument("--table", choices=("rosmaster", "rassmaster"), default="rosmaster")
        service.add_argument("--radius" if name == "cone" else "--size", type=float, default=1,
                             help="Cone radius or image search width in degrees")
    links = commands.add_parser("datalink", help="Resolve a HEASARC DataLink URL from image results")
    links.add_argument("url")
    sources = commands.add_parser("sources", help="Search the 2RXS detection catalogue")
    coordinates(sources)
    sources.add_argument("--radius-arcsec", type=float, default=90)
    upper = commands.add_parser("limit", help="Retrieve ROSAT measurements and limits from HiLIGT")
    coordinates(upper)
    upper.add_argument("--mission", choices=("RosatSurvey", "RosatPointedPSPC", "RosatPointedHRI"),
                       default="RosatSurvey")
    upper.add_argument("--sigma", choices=(1, 2, 3), type=int, default=3)
    obs = commands.add_parser("observations", help="Search observation centres; writes VOTable XML")
    coordinates(obs)
    obs.add_argument("--table", choices=["rosmaster", "rassmaster"], default="rosmaster")
    obs.add_argument("--radius", type=float, default=1, help="Cone radius in degrees")
    listing = commands.add_parser("products", help="List files and child prefixes as JSON")
    group = listing.add_mutually_exclusive_group(required=True)
    group.add_argument("--prefix", help="Archive directory, e.g. rosat/data/")
    group.add_argument("--sequence", help="Pointed PSPC/HRI dataset, e.g. rp500065n00")
    download_command(commands)
    args = parser.parse_args()
    if args.command == "sources":
        print(json.dumps(query_survey("rosat", args.ra, args.dec, args.radius_arcsec), indent=2))
        return
    if args.command == "limit":
        print(json.dumps(query_hiligt(args.ra, args.dec, args.mission, sigma=args.sigma), indent=2))
        return
    if args.command in ("cone", "images", "tap", "datalink"):
        base = "https://heasarc.gsfc.nasa.gov/xamin/vo/"
        if args.command == "datalink":
            location = urlsplit(args.url)
            if (location.scheme, location.netloc, location.path) != (
                    "https", "heasarc.gsfc.nasa.gov", "/xamin/vo/datalink"):
                parser.error("Expected the HTTPS DataLink URL returned by HEASARC")
            url = args.url
        elif args.command == "tap":
            url = TAP + "?" + urlencode(dict(REQUEST="doQuery", LANG="ADQL", FORMAT="votable", QUERY=args.query))
        else:
            validate_position(args.ra, args.dec)
            extent = args.radius if args.command == "cone" else args.size
            if not 0 < extent <= 180:
                parser.error("Expected an angular extent in (0,180] degrees")
            if args.command == "cone":
                url = base + "cone?" + urlencode(dict(table=args.table, RA=args.ra, DEC=args.dec, SR=extent))
            else:
                url = base + "sia?" + urlencode(dict(table=args.table, POS=f"{args.ra},{args.dec}", SIZE=extent))
        try:
            votable(url, {})
        except (URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, HTTPError) and exc.code < 500:
                raise
            retry = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--max-time", "90", url],
                                   stdout=subprocess.PIPE)
            if retry.returncode:
                raise OSError(f"curl returned {retry.returncode} after {exc}") from exc
            write_votable(retry.stdout)
        return
    if args.command == "download":
        download(args.url, args.output, {"nasa-heasarc.s3.amazonaws.com", "heasarc.gsfc.nasa.gov"})
    elif args.command == "products":
        prefix = args.prefix
        if args.sequence:
            seq = args.sequence.lower()
            if not re.fullmatch(r"r[ph]\d{6}[a-z]\d{2}", seq):
                parser.error("Expected a pointed PSPC or HRI sequence such as rp500065n00")
            instrument = "pspc" if seq[1] == "p" else "hri"
            prefix = f"rosat/data/{instrument}/processed_data/{seq[2]}00000/{seq}/"
        print(json.dumps(list(products(prefix)), indent=2))
    else:
        validate_position(args.ra, args.dec)
        if not 0 < args.radius <= 180:
            parser.error("Radius must be in (0,180] degrees")
        query = (f"SELECT * FROM {args.table} WHERE 1=CONTAINS(POINT('ICRS',ra,dec),"
                 f"CIRCLE('ICRS',{args.ra},{args.dec},{args.radius}))")
        params = {"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query, "FORMAT": "votable"}
        try:
            votable(TAP, params)
        except (URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, HTTPError) and error.code < 500:
                raise
            print(f"Python TAP request failed ({error}); retrying TAP with curl.", file=sys.stderr)
            try:
                result = subprocess.run(
                    ["curl", "--silent", "--show-error", "--fail", "--connect-timeout", "10",
                     "--max-time", "90", TAP + "?" + urlencode(params)],
                    stdout=subprocess.PIPE, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError) as curl_error:
                if args.table != "rosmaster":
                    raise OSError(f"TAP retry failed: {curl_error}") from error
            else:
                write_votable(result.stdout)
                return
            print("HEASARC TAP unavailable; searching NASA's PSPC/HRI archive indexes.", file=sys.stderr)
            pointed_index(args.ra, args.dec, args.radius)


if __name__ == "__main__":
    cli(main)
