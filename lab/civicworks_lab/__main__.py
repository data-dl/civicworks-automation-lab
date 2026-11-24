"""python -m civicworks_lab [--port 8870] [--no-browser]"""

import argparse
import webbrowser

from .server import serve

parser = argparse.ArgumentParser(prog="civicworks_lab", description="Run and study the CivicWorks pipelines.")
parser.add_argument("--port", type=int, default=8870)
parser.add_argument("--no-browser", action="store_true")
args = parser.parse_args()
try:
    serve(args.port, open_browser=not args.no_browser)
except OSError:
    # The port is taken: the Lab is most likely already running, so open it instead of failing silently.
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    else:
        raise
