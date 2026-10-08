"""Start Social Climb and open it in the browser.

This is also the entry point of the packaged SocialClimb.exe.
Options: --port 8000, --local-only (refuse phone connections), --no-browser.
"""
import argparse
import socket
import sys
import threading
import webbrowser

import uvicorn

from backend.main import create_app
from backend.network import lan_ip


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--local-only", action="store_true", help="don't accept connections from your phone")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = f"http://localhost:{args.port}"

    if port_in_use(args.port):
        # Most likely Social Climb is already running: just show it.
        print(f"Social Climb is already running at {url}")
        webbrowser.open(url)
        return

    app = create_app()
    print("\n  Social Climb is running. Keep this window open while you use it;")
    print("  close it to stop the app.\n")
    print(f"  On this computer: {url}")
    if not args.local_only:
        print(f"  Phone (same Wi-Fi): http://{lan_ip()}:{args.port}  - easiest: scan the QR code in the app\n")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    host = "127.0.0.1" if args.local_only else "0.0.0.0"
    uvicorn.run(app, host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # keep the window open so the error can be read
        print(f"\nSocial Climb could not start: {exc}")
        if getattr(sys, "frozen", False):
            input("Press Enter to close...")
        raise
