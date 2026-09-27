"""Serve the built paper console and public-data paper scanner on loopback with watchdog."""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.paper.local_server import serve


def main():
    parser = argparse.ArgumentParser(description="Local paper-only market console")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--watchdog", action="store_true", help="Auto-restart server if it terminates unexpectedly")
    args = parser.parse_args()

    if not args.watchdog:
        serve(port=args.port, open_browser=args.open_browser)
        return

    first_run = True
    while True:
        try:
            serve(port=args.port, open_browser=args.open_browser if first_run else False)
            break
        except KeyboardInterrupt:
            print("\n[Watchdog] Operator stopped the service.", flush=True)
            break
        except Exception as exc:
            first_run = False
            print(f"\n[Watchdog] Server exited unexpectedly: {exc}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
