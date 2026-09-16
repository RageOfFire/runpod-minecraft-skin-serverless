import argparse
import base64
import os
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Minecraft skin from text, an image, or both."
    )
    parser.add_argument("prompt", nargs="?", default="")
    parser.add_argument("--image", help="Optional reference PNG/JPG/WebP/GIF")
    parser.add_argument("--reference-strength", type=float, default=0.70)
    parser.add_argument("--endpoint", default=os.getenv("RUNPOD_ENDPOINT_ID"))
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"))
    parser.add_argument("--output", default="skin.png")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--steps", type=int, default=35)
    args = parser.parse_args()

    if not args.endpoint or not args.api_key:
        raise SystemExit(
            "Set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY, or pass --endpoint/--api-key"
        )
    if not args.prompt and not args.image:
        raise SystemExit("Provide a prompt, --image, or both")

    payload = {
        "input": {
            "prompt": args.prompt,
            "steps": args.steps,
            "format": "modern",
        }
    }

    if args.image:
        raw = Path(args.image).read_bytes()
        if len(raw) > 6 * 1024 * 1024:
            raise SystemExit("Reference image must be 6 MB or smaller")
        payload["input"]["reference_image_base64"] = base64.b64encode(raw).decode("ascii")
        payload["input"]["reference_strength"] = args.reference_strength

    if args.seed is not None:
        payload["input"]["seed"] = args.seed

    response = requests.post(
        f"https://api.runpod.ai/v2/{args.endpoint}/runsync?wait=300000",
        headers={
            "Authorization": f"Bearer {args.api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=330,
    )
    response.raise_for_status()
    body = response.json()

    if body.get("status") != "COMPLETED":
        raise RuntimeError(body)

    output = body["output"]
    raw = base64.b64decode(output["image_base64"])
    Path(args.output).write_bytes(raw)
    print(
        f"Saved {args.output} ({output['width']}x{output['height']}, "
        f"seed={output['seed']}, mode={output.get('source_mode', 'unknown')})"
    )


if __name__ == "__main__":
    main()
