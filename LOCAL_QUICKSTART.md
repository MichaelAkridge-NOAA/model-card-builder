# Local Quickstart

This guide is for running Model Card Builder locally.

## Prerequisites

- Python 3.9+
- pip
- Optional for AI enrichment: GITHUB_TOKEN with GitHub Models access

## Setup

1. Install requirements:

   ```powershell
   pip install -r requirements.txt
   ```

2. Fetch model-card data from Hugging Face:

   ```powershell
   python python/fetch_hf_model_card.py https://huggingface.co/org/model
   ```

   This writes model_data.json using the typed Model Card Data shape.

3. Build HTML model card from local data:

   ```powershell
   python python/build.py --data model_data.json
   ```

4. Optional AI enrichment with prompts:

   ```powershell
   $env:GITHUB_TOKEN = "<token with models access>"
   python python/summarize_model_card.py --url https://huggingface.co/org/model --data model_data.json --prompt prompts/summarize.prompt.yaml --recovery-prompt prompts/recover_model_card_facets.prompt.yaml
   ```

5. One-step flow from URL to HTML:

   ```powershell
   python python/build.py --url https://huggingface.co/org/model --template standard --theme noaa
   ```

## Notes

- Local output HTML is written to Model_Card.html in the repository root.
- The GitHub Actions workflow handles gallery updates and publishing automatically.
