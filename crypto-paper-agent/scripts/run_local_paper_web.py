"""Serve the built paper console and public-data paper scanner on loopback."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.paper.local_server import serve


def main():
    parser = argparse.ArgumentParser(description="Local paper-only market console")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    serve(port=args.port, open_browser=args.open_browser)


if __name__ == "__main__":
    main()
