import argparse
import re
from pathlib import Path

from .generator import CLOUD_NOTES, generate, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("requirement")
    parser.add_argument("--cloud", choices=CLOUD_NOTES, default="aws")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev")
    args = parser.parse_args()

    print("Generating, this takes a minute...")
    result = generate(args.requirement, args.cloud, args.env)

    slug = re.sub(r"[^a-z0-9]+", "-", args.requirement.lower()).strip("-")[:40]
    folder = Path("output") / slug
    save(result, folder)

    cost = result.get("cost", {})
    print(result.get("summary", ""))
    print(f"Estimated cost: ${cost.get('monthly_usd')}/month (typical: ${cost.get('typical_usd')})")
    print(f"Security controls: {len(result.get('security', []))} | Flow steps: {len(result.get('flow', []))}")
    print(f"Files saved in: {folder}")


if __name__ == "__main__":
    main()