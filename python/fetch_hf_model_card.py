import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from python.model_card_data import fetch_model_card_data, save_model_card_data


def fetch_model_card(url_or_id: str, output_path: Optional[str] = None) -> str:
    """Fetch model card data from Hugging Face and save the typed contract as JSON."""
    repo_root = Path(__file__).resolve().parent.parent
    if output_path is None:
        output_path = str(repo_root / "model_data.json")

    model_card_data = fetch_model_card_data(url_or_id)
    save_model_card_data(model_card_data, output_path)
    print(f"Saved model data to {output_path}")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Hugging Face model card data into the typed Model Card Data contract."
    )
    parser.add_argument("url_or_repo_id", help="Hugging Face model URL or org/model repo id")
    parser.add_argument("--output", "-o", help="Output path for model_data.json")
    args = parser.parse_args()

    fetch_model_card(args.url_or_repo_id, output_path=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
