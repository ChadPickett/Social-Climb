"""Start Social Climb: python run.py [--port 8000] [--local-only]"""
import argparse
import socket

import uvicorn


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--local-only", action="store_true", help="don't accept connections from your phone")
    args = parser.parse_args()
    host = "127.0.0.1" if args.local_only else "0.0.0.0"
    print(f"\n  PC:    http://localhost:{args.port}")
    if not args.local_only:
        print(f"  Phone: http://{lan_ip()}:{args.port}  (same Wi-Fi)\n")
    uvicorn.run("backend.main:create_app", factory=True, host=host, port=args.port)
