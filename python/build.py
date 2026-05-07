import sys
import argparse
import os
from pathlib import Path

from python.fetch_hf_model_card import fetch_model_card
from python.html_renderer import render_card_document
from python.model_card_data import load_model_card_data, with_assets_dir
from python.model_card_document import SUPPORTED_TEMPLATES, SUPPORTED_THEMES, build_card_document


def build_model_card(
    model_data_path,
    output_path=None,
    assets_dir=None,
    template="standard",
    theme="noaa",
):
    """Build a model card HTML document from typed model data."""
    repo_root = Path(__file__).resolve().parent.parent
    if assets_dir is None:
        assets_dir = str(repo_root / "assets")
    if output_path is None:
        output_path = str(repo_root / "Model_Card.html")

    if not os.path.exists(model_data_path):
        print(f"Error: Model data file not found at {model_data_path}")
        return False

    model_card_data = load_model_card_data(model_data_path)
    model_card_data = with_assets_dir(model_card_data, assets_dir)
    document = build_card_document(
        model_card_data=model_card_data,
        template=template,
        theme=theme,
    )
    render_card_document(document, output_path)
    print(f"Model card HTML created at: {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build a model card HTML document from a Hugging Face model")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", "-u", help="URL of the Hugging Face model")
    group.add_argument("--data", "-d", help="Path to existing model_data.json file")
    parser.add_argument("--output", "-o", help="Output path for the HTML file")
    parser.add_argument("--assets", "-a", help="Directory containing asset files (images)")
    parser.add_argument(
        "--template",
        default="standard",
        choices=sorted(SUPPORTED_TEMPLATES),
        help="Named template used to build the Card Document",
    )
    parser.add_argument(
        "--theme",
        default="noaa",
        choices=sorted(SUPPORTED_THEMES),
        help="Named theme used by the HTML renderer",
    )
    args = parser.parse_args()

    if args.url:
        try:
            model_data_path = fetch_model_card(args.url)
        except Exception as e:
            print(f"Error fetching model card data: {e}")
            return 1
    else:
        model_data_path = args.data

    # Build the model card
    success = build_model_card(
        model_data_path=model_data_path,
        output_path=args.output,
        assets_dir=args.assets,
        template=args.template,
        theme=args.theme,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
