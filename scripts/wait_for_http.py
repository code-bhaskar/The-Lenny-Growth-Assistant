from __future__ import annotations

import argparse
import sys
import time

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--expect-text", default=None)
    args = parser.parse_args()

    deadline = time.time() + args.timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = requests.get(args.url, timeout=5)
            if response.ok and (args.expect_text is None or args.expect_text in response.text):
                print(f"READY {args.url}")
                return 0
            last_error = f"status={response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(2)

    print(f"TIMEOUT {args.url} :: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
