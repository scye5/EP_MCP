"""Find historical X-ray detections and upper limits at an EP candidate position."""
import argparse
import json

from archive import MISSIONS, query_hiligt
from archive_io import cli, coordinates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("missions", help="List accepted mission identifiers")
    query = commands.add_parser("query", help="Retrieve observation-band rows as JSON")
    coordinates(query)
    query.add_argument("--mission", choices=MISSIONS, default="XMMpnt")
    query.add_argument("--sigma", choices=(1, 2, 3), type=int, default=3)
    spectrum = query.add_mutually_exclusive_group()
    spectrum.add_argument("--power-law-slope", type=float, default=1.7)
    spectrum.add_argument("--blackbody-ev", type=int, choices=(60, 100, 300, 1000))
    query.add_argument("--nh-cm2", type=float, choices=(1e20, 3e20, 1e21), default=3e20)
    query.add_argument("--no-catalogue", action="store_true", help="Send usecat=no to HiLIGT")
    args = parser.parse_args()
    if args.command == "missions":
        print("\n".join(MISSIONS))
        return
    result = query_hiligt(args.ra, args.dec, args.mission, args.sigma, args.power_law_slope,
                          args.nh_cm2, args.blackbody_ev, not args.no_catalogue)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    cli(main)
