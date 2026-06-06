#!/usr/bin/env python3
import sys

from auto_broll.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["doctor", *sys.argv[1:]]))
