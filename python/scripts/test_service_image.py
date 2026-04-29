from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/solve")
    args = parser.parse_args()

    image_path = Path(args.image).expanduser()

    with image_path.open("rb") as f:
        files = {
            "image": (image_path.name, f, "image/jpeg"),
        }
        data = {
            "metadata_json": json.dumps(
                {
                    "source": "test_service_image.py",
                    "image_path": str(image_path),
                }
            )
        }
        r = requests.post(args.url, files=files, data=data, timeout=90)

    print("HTTP", r.status_code)
    print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    main()
