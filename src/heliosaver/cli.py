import argparse
import json

from .fits import process_helioviewer_fits
from .png import save_images_by_date_png


def main():
    p = argparse.ArgumentParser(prog="heliosaver")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_fits = sub.add_parser("fits", help="Download JP2 + header and write FITS.")
    p_fits.add_argument("--source-id", type=int, required=True)
    p_fits.add_argument("--out", type=str, default=".")
    p_fits.add_argument("--date", action="append", required=True,
                        help="ISO date, can be given multiple times.")
    p_fits.add_argument("--no-header-txt", action="store_true")

    p_png = sub.add_parser("png", help="Download JP2 and write PNG into date folders.")
    p_png.add_argument("--source-id", type=int, required=True)
    p_png.add_argument("--out", type=str, default=".")
    p_png.add_argument("--date", action="append", required=True,
                       help="ISO date, can be given multiple times.")

    args = p.parse_args()

    if args.cmd == "fits":
        res = process_helioviewer_fits(
            dates=args.date,
            source_id=args.source_id,
            output_path=args.out,
            save_header_txt=not args.no_header_txt,
        )
        print(json.dumps(res, indent=2))
    elif args.cmd == "png":
        res = save_images_by_date_png(
            dates=args.date,
            source_id=args.source_id,
            base_output_path=args.out,
        )
        print(json.dumps(res, indent=2))
