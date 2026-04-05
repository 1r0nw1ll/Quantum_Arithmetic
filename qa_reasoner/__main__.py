"""
CLI for qa_reasoner.

    python -m qa_reasoner classify 1 1 --mod 9
    python -m qa_reasoner invariants 3 5
    python -m qa_reasoner witness 1 1 3 5 --mod 9
    python -m qa_reasoner explain 2 3 --mod 9
    python -m qa_reasoner stats --mod 24
    python -m qa_reasoner match 1,1 2,3 3,5 --mod 9
"""

from __future__ import annotations

import argparse
import json
import sys

from .reasoner import QAReasoner
from .patterns import PatternMatcher


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    p = argparse.ArgumentParser(prog="qa_reasoner", description="Discrete QA reasoner CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    for cmd in ("classify", "invariants", "explain"):
        c = sub.add_parser(cmd)
        c.add_argument("b", type=int)
        c.add_argument("e", type=int)
        c.add_argument("--mod", type=int, default=9)

    cw = sub.add_parser("witness")
    cw.add_argument("sb", type=int)
    cw.add_argument("se", type=int)
    cw.add_argument("tb", type=int)
    cw.add_argument("te", type=int)
    cw.add_argument("--mod", type=int, default=9)
    cw.add_argument("--generators", default="Q", help="comma-separated, e.g. 'Q' or 'Q,T'")

    cs = sub.add_parser("stats")
    cs.add_argument("--mod", type=int, default=9)

    cm = sub.add_parser("match")
    cm.add_argument("examples", nargs="+", help="pairs like 1,1 2,3 3,5")
    cm.add_argument("--mod", type=int, default=9)

    args = p.parse_args(argv)
    r = QAReasoner(args.mod)

    if args.cmd == "classify":
        _print(r.classify(args.b, args.e).to_dict())
    elif args.cmd == "invariants":
        _print(r.invariants(args.b, args.e))
    elif args.cmd == "explain":
        _print(r.explain(args.b, args.e))
    elif args.cmd == "witness":
        gens = tuple(g.strip().upper() for g in args.generators.split(","))
        _print(r.witness((args.sb, args.se), (args.tb, args.te), generators=gens).to_dict())
    elif args.cmd == "stats":
        _print({
            "modulus": args.mod,
            "orbit_counts": r.orbit_statistics(),
        })
    elif args.cmd == "match":
        pairs = []
        for x in args.examples:
            a, b = x.split(",")
            pairs.append((int(a), int(b)))
        pm = PatternMatcher(m=args.mod)
        _print(pm.match(pairs))
    else:
        p.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
