# NOAA Model Card Template
A Python-based model card builder that fetches Hugging Face metadata into a typed **Model Card Data** contract, builds a format-neutral **Card Document**, and renders an HTML model card using named templates and themes.

![Example Model Card](./assets/model_card_template_example.png)

## Features
- 📊 Clean, modern single-page HTML layout
- 🎨 NOAA/NMFS branded design with official colors
- 🧱 Typed model-card contract and section-based document builder
- 🧩 Named template and theme interface for future renderers
- 📱 Responsive column layout
- 🔄 Automated GitHub Actions workflow
- 📈 Support for data visualization
- 🎯 Focus on key metrics and explanations
- 🌐 Live gallery published via GitHub Pages

### Live Model Gallery

View all generated model cards in the **[Live Gallery](https://MichaelAkridge-NOAA.github.io/model-card-template/gallery/)**

The gallery:
- Updates automatically whenever a new model card is generated
- Provides searchable, filterable index of all models
- Displays model cards with metadata and metrics
- Works instantly with client-side search (no server required)

**Gallery URL:** https://MichaelAkridge-NOAA.github.io/model-card-template/gallery/

For GitHub Pages setup details, see [GITHUB_PAGES_SETUP.md](./GITHUB_PAGES_SETUP.md)

### How to Use

1. **Install Requirements:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Fetch model-card data:**
   ```powershell
   python fetch_hf_model_card.py https://huggingface.co/org/model
   ```
   This writes `model_data.json` in the typed **Model Card Data** shape, with README-first extraction for overview, intended use, deployment, limitations, metrics, and real model asset URLs when available.

3. **Render the model card:**
   ```
   python build.py --data model_data.json
   ```
   This writes `Model_Card.html` in the repository root.

4. **Optional summary enrichment with GitHub Models:**
   ```powershell
   $env:GITHUB_TOKEN = "<token with models access>"
   python summarize_model_card.py --url https://huggingface.co/org/model --data model_data.json --prompt summarize.prompt.yaml --recovery-prompt recover_model_card_facets.prompt.yaml
   ```
   This augments `model_data.json` with a generated summary, then optionally runs a targeted recovery pass for missing metrics or representative visuals when the completeness assessor finds gaps.

5. **One-step flow from a Hugging Face URL:**
   ```powershell
   python build.py --url https://huggingface.co/org/model --template standard --theme noaa
   ```

6. **GitHub Actions trigger policy:**
   - `workflow_dispatch` can always be used manually.
   - Issue-driven generation only runs when a maintainer applies the `generate-model-card` label to an issue that contains a Hugging Face URL.

### Template Features
- Clean, one-page layout
- NOAA/NMFS branded design
- Format-neutral **Card Document** built from structured sections and blocks
- README-first model card extraction with frontmatter parsing and richer metric capture
- Optional GitHub Models summarization step driven by `summarize.prompt.yaml`
- HTML renderer adapter with room for future adapters such as PDF
- All key model card sections
- Easy to edit and extend

---

- https://github.com/tensorflow/model-card-toolkit
- https://modelcards.withgoogle.com/
----------
#### Disclaimer
This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project content is provided on an ‘as is’ basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.

#### License
- Details in the [LICENSE.md](./LICENSE.md) file.
