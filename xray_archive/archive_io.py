"""HTTP and CLI helpers for the mission archive clients (Python 3.10+)."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


def coordinates(parser):
    parser.add_argument("ra", type=float, help="ICRS right ascension in degrees")
    parser.add_argument("dec", type=float, help="ICRS declination in degrees")


def validate_position(ra, dec):
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise ValueError("Expected RA in [0,360) and Dec in [-90,90]")


def request(url, params=None, body=None):
    if params:
        url += "?" + urlencode(params)
    data = None if body is None else json.dumps(body, allow_nan=False).encode()
    headers = {"Content-Type": "application/json"} if data is not None else {}
    return urlopen(Request(url, data=data, headers=headers), timeout=90)


def votable(url, params):
    with request(url, params) as stream:
        data = stream.read()
    write_votable(data)


def write_votable(data):
    root = ET.fromstring(data)
    if root.tag.split("}")[-1] != "VOTABLE":
        raise ValueError("Archive did not return a VOTable")
    for info in root.findall(".//{*}INFO") + root.findall(".//{*}PARAM"):
        if info.get("name", "").lower() == "error" or info.get("value") == "ERROR":
            raise ValueError(f"Archive error: {info.text or info.get('value')}")
    sys.stdout.buffer.write(data)


def download_command(commands):
    command = commands.add_parser("download", help="Save an archive product by URL")
    command.add_argument("url")
    command.add_argument("output", type=Path)


def download(url, output, hosts):
    location = urlsplit(url)
    if location.scheme != "https" or location.hostname not in hosts:
        raise ValueError("Expected an HTTPS URL on the mission archive")
    if output.exists():
        raise FileExistsError(output)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as tmp:
        staging = Path(tmp.name)
    try:
        with request(url) as stream, staging.open("wb") as handle:
            if stream.headers.get_content_type() == "text/html":
                raise ValueError("Archive returned an HTML page instead of a file")
            shutil.copyfileobj(stream, handle, length=1024 * 1024)
            expected = stream.headers.get("Content-Length")
            if expected is not None and handle.tell() != int(expected):
                raise IOError("Incomplete download")
        os.link(staging, output)  # Publish only complete files, without replacing existing data.
    finally:
        staging.unlink(missing_ok=True)


def cli(main):
    try:
        main()
    except (OSError, ValueError, ET.ParseError) as exc:
        sys.exit(f"Archive request failed: {exc}")
