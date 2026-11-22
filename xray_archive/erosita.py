"""eRODat catalogue, coverage, upper-limit and file services."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from archive_io import cli, coordinates, download, download_command, request, validate_position, votable

BASE = "https://erosita.mpe.mpg.de/erodat/"
BANDS = {"DR1_eRASS1": ("021", "022", "023", "024", "02e"), "DR2_eRASSc3": ("023", "024")}


class ProductLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.files = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and re.fullmatch(r"[\w.-]+\.(?:fits|fit|fts)(?:\.gz)?", href, re.I):
            self.files.append(href)


def limits(row):
    validate_position(row["ra"], row["dec"])
    survey = row.get("dr_survey", "DR1_eRASS1")
    if row["band"] not in BANDS.get(survey, ()):
        raise ValueError(f"Invalid band for {survey}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cone = commands.add_parser("cone", help="Write catalogue cone search as VOTable XML")
    coordinates(cone)
    cone.add_argument("--catalog", choices=("DR1_Main", "DR1_Hard", "DR1_Supp", "DR1_Clusters",
                                            "DR2_Main", "DR2_Hard"), default="DR2_Main")
    cone.add_argument("--radius", type=float, default=0.025, help="Degrees, maximum 5")
    cone.add_argument("--verb", type=int, choices=(1, 2, 3), default=3, help="Catalogue column verbosity")
    tiles = commands.add_parser("tiles")
    coordinates(tiles)
    tiles.add_argument("--radius", type=float, default=0, help="Degrees; zero for a point")
    upper = commands.add_parser("limit")
    coordinates(upper)
    upper.add_argument("--band", default="024")
    upper.add_argument("--survey", choices=BANDS, default="DR1_eRASS1")
    batch = commands.add_parser("limits")
    batch.add_argument("json_file", type=Path)
    listing = commands.add_parser("products", help="List FITS products in a DR1 tile directory")
    listing.add_argument("tile", help="Six-digit srvmap from tiles")
    listing.add_argument("group", help="Product directory, e.g. DET_010")
    download_command(commands)
    args = parser.parse_args()
    if hasattr(args, "ra"):
        validate_position(args.ra, args.dec)
    if args.command == "download":
        return download(args.url, args.output, {"erosita.mpe.mpg.de"})
    if args.command == "cone":
        if not 0 < args.radius <= 5:
            parser.error("Cone radius must be in (0,5] degrees")
        return votable(BASE + "catalogue/SCS", dict(CAT=args.catalog, RA=args.ra, DEC=args.dec,
                                                    SR=args.radius, VERB=args.verb))
    if args.command == "products":
        if not re.fullmatch(r"\d{6}", args.tile) or not re.fullmatch(r"[A-Z]+_\d{3}", args.group):
            parser.error("Expected a six-digit tile and product directory such as DET_010")
        directory = BASE + f"data/download/{args.tile[3:]}/{args.tile[:3]}/{args.group}/"
        links = ProductLinks()
        with request(directory) as stream:
            links.feed(stream.read().decode("utf-8"))
        print(json.dumps([urljoin(directory, name) for name in links.files], indent=2))
        return
    if args.command == "tiles":
        if not 0 <= args.radius <= 180:
            parser.error("Radius must be in [0,180] degrees")
        response = request(BASE + "skyview/skytile_search_api/", dict(RA=args.ra, DEC=args.dec, RAD=args.radius))
    elif args.command == "limit":
        row = dict(ra=args.ra, dec=args.dec, band=args.band, dr_survey=args.survey)
        limits(row)
        response = request(BASE + "upperlimit/service", row)
    else:
        rows = json.loads(args.json_file.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
            parser.error("Supply a JSON array of 1 to 10000 lookups")
        for row in rows:
            if not isinstance(row, dict) or not {"ra", "dec", "band"} <= row.keys():
                parser.error("Each lookup requires ra, dec and band")
            limits(row)
        response = request(BASE + "upperlimit/service_multi", body=rows)
    with response:
        result = json.load(response)
    if str(result.get("error")).lower() != "none":
        raise ValueError(result["error"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    cli(main)
