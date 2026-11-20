"""Render the v3 scoring request for a title and text with verified image notes."""

import argparse
import json
from pathlib import Path


def build_request(title, body):
    system = Path(__file__).with_name("system_prompt.txt").read_text(encoding="utf-8")
    text = f"Title:\n{title}\n\nBody and verified image notes:\n{body}"
    return {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
        "stream": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--body",
        type=Path,
        required=True,
        help="UTF-8 file containing the post body and verified image notes",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build_request(args.title, args.body.read_text(encoding="utf-8")),
            ensure_ascii=False,
            indent=2,
        )
    )
