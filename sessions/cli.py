"""命令行入口：跑会话管理样例。"""

import argparse

from .core import Sessions


def build_parser():
    parser = argparse.ArgumentParser(prog="session-eviction", description="会话管理")
    parser.add_argument("--sample", default="limit", help="limit / keep / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "limit":
        book = Sessions(max_sessions=2)
        for index, player in enumerate(["a", "b", "c"]):
            book.open(player, index)
        print("size=%d evicted=%d" % (book.size(), book.evicted))
    elif args.sample == "keep":
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 0)
        print("reconnected=%s" % str(book.reconnect("a", 20000)).lower())
    elif args.sample == "scan":
        book = Sessions(max_sessions=100000)
        for index in range(3000):
            book.open("p-%d" % index, index)
        for _ in range(3000):
            book.size()
        print("scanned=%d" % book.scanned_count())
    else:
        raise SystemExit("需要 --sample limit|keep|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
