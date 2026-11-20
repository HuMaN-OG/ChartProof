"""Command-line audit of two chart files, using their printed percentage labels."""
import argparse
import json
from pathlib import Path
from .images import picture, extract_local, assemble
from .verify import compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("original", type=Path)
    p.add_argument("revision", type=Path)
    p.add_argument("--claim", action="append", required=True)
    p.add_argument("--original-page", type=int, default=1)
    p.add_argument("--revision-page", type=int, default=1)
    p.add_argument("--out", type=Path, help="Export a reviewable audit JSON for the web workspace")
    args = p.parse_args()

    def read(path, page):
        if path.stat().st_size > 6*1024*1024:
            raise ValueError("File exceeds 6 MiB.")
        data = path.read_bytes()
        im, count = picture(data, page)
        return {**assemble(data, page, im, count, extract_local(im)), "filename": path.name}
    a = read(args.original, args.original_page)
    b = read(args.revision, args.revision_page)
    results = [compare(t, a, b) for t in args.claim]
    audit = {"schema": 1, "before": a, "after": b, "claims": args.claim, "results": results, "history": []}
    print("Automatic OCR reading; inspect the source evidence before publication.")
    for result in results:
        print(result["transition"], "|", result["claim"])
        for side in ("before", "after"):
            v = result[side]
            print(f"  {side}: {v['status']} | {v['formula'] or v['reason']}")
    if args.out:
        args.out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    revised_statuses = {result["after"]["status"] for result in results}
    if "Contradicted" in revised_statuses:
        return 1
    if "Insufficient evidence" in revised_statuses:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
