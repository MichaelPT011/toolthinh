"""Write the stable latest.json manifest used by the in-app updater."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--notes", default="Ban cap nhat moi tu GitHub Releases.")
    args = parser.parse_args()

    manifest = {
        "version": args.version,
        "channel": "stable",
        "name": "Tool Veo3's Thinh",
        "notes": args.notes,
        "windows_url": f"https://github.com/{args.repo}/releases/download/{args.tag}/Tool-Veo3s-Thinh-win.zip",
        "mac_url": f"https://github.com/{args.repo}/releases/download/{args.tag}/Tool-Veo3s-Thinh-mac.zip",
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
