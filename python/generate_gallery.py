#!/usr/bin/env python
"""
Gallery generator script that builds a static HTML gallery from the model card registry.

Reads gallery/cards.json and generates gallery/index.html with embedded search/filter logic.
"""

import argparse
import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=True)


def group_cards_by_pipeline(cards: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group cards by pipeline_type.
    
    Args:
        cards: List of card objects from registry
        
    Returns:
        Dictionary mapping pipeline_type to list of cards
    """
    grouped = {}
    for card in cards:
        pipeline_type = card.get("pipeline_type", "other")
        if pipeline_type not in grouped:
            grouped[pipeline_type] = []
        grouped[pipeline_type].append(card)
    return grouped


def validate_card(card: Dict) -> Tuple[bool, str]:
    """
    Validate that a card has all required fields.
    
    Args:
        card: Card object to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["model_id", "model_name", "description", "organization", "pipeline_type", "card_url"]
    missing = [f for f in required_fields if f not in card or not card[f]]
    
    if missing:
        return False, f"Card missing required fields: {', '.join(missing)}"
    
    return True, ""


def generate_gallery_html(registry_path: str, output_path: str) -> Tuple[bool, str, int]:
    """
    Generate static gallery HTML from registry.
    
    Args:
        registry_path: Path to gallery/cards.json
        output_path: Path to output gallery/index.html
        
    Returns:
        Tuple of (success, message, card_count)
    """
    # Check if registry exists
    if not os.path.exists(registry_path):
        return False, f"Registry file not found: {registry_path}", 0
    
    # Read registry
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Failed to parse registry JSON: {e}", 0
    except Exception as e:
        return False, f"Failed to read registry: {e}", 0
    
    # Extract cards
    cards = registry.get("cards", [])
    
    if not cards:
        # Generate empty gallery
        html_content = _generate_empty_gallery_html()
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            return True, "Generated empty gallery (no cards in registry)", 0
        except Exception as e:
            return False, f"Failed to write output: {e}", 0
    
    # Validate all cards
    for i, card in enumerate(cards):
        is_valid, error_msg = validate_card(card)
        if not is_valid:
            return False, f"Card {i} validation failed: {error_msg}", 0
    
    # Group cards by pipeline
    grouped = group_cards_by_pipeline(cards)
    
    # Generate HTML
    try:
        html_content = _generate_gallery_html_content(cards, grouped)
        
        # Write output
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return True, f"Generated gallery with {len(cards)} model(s)", len(cards)
    
    except Exception as e:
        return False, f"Failed to generate gallery: {e}", 0


def _generate_empty_gallery_html() -> str:
    """Generate HTML for empty gallery."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOAA Model Gallery</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: Arial, Helvetica, sans-serif;
            background: #f3f7fb;
            color: #1a1a1a;
            line-height: 1.6;
        }

        .page {
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px 24px 48px;
        }

        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 24px;
            border-bottom: 2px solid #d5e2ef;
        }

        .logo {
            max-width: 240px;
            margin: 0 auto 18px;
            height: auto;
        }

        h1 {
            font-size: 2.4rem;
            color: #005cb9;
            margin-bottom: 8px;
        }

        .subtitle {
            color: #34495e;
            font-size: 1rem;
        }

        .empty-message {
            text-align: center;
            padding: 60px 24px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(0, 56, 101, 0.08);
        }

        .empty-message p {
            color: #34495e;
            font-size: 1.1rem;
            margin: 16px 0;
        }

        footer {
            text-align: center;
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid #d5e2ef;
            color: #7f8c8d;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="page">
        <header>
            <img src="assets/NOAA_FISHERIES_logoH_web.png" alt="NOAA Fisheries" class="logo">
            <h1>Model Gallery</h1>
            <p class="subtitle">NOAA Model Card Registry</p>
        </header>

        <main>
            <div class="empty-message">
                <p>📦 No model cards yet</p>
                <p>The gallery will appear here as model cards are added to the registry.</p>
            </div>
        </main>

        <footer>
            Generated by <strong>NOAA Model Card Template</strong> | 
            <a href="https://github.com/MichaelAkridge-NOAA/model-card-template">GitHub</a>
        </footer>
    </div>
</body>
</html>
"""


def _generate_gallery_html_content(cards: List[Dict], grouped: Dict[str, List[Dict]]) -> str:
    """
    Generate the full gallery HTML content with embedded CSS and JavaScript.
    
    Args:
        cards: List of all cards
        grouped: Cards grouped by pipeline_type
        
    Returns:
        Complete HTML string
    """
    
    # Sort pipeline types for consistent order
    pipeline_types = sorted(grouped.keys())
    
    # Generate pipeline options for dropdown
    pipeline_options = '\n                        '.join(
        f'<option value="{pipeline}">{_format_pipeline_name(pipeline)}</option>'
        for pipeline in pipeline_types
    )
    
    # Generate card sections
    sections_html = []
    for pipeline_type in pipeline_types:
        pipeline_cards = grouped[pipeline_type]
        cards_html = '\n            '.join(
            _generate_card_html(card) for card in pipeline_cards
        )
        
        section = f'''
        <section class="pipeline-section" data-pipeline="{escape_html(pipeline_type)}">
            <h2>{_format_pipeline_name(pipeline_type)}</h2>
            <div class="card-grid">
                {cards_html}
            </div>
        </section>
        '''
        sections_html.append(section)
    
    sections_html_str = ''.join(sections_html)
    
    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOAA Model Gallery</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: Arial, Helvetica, sans-serif;
            background: #f3f7fb;
            color: #1a1a1a;
            line-height: 1.6;
        }}

        .page {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 0;
        }}

        header {{
            background: white;
            border-bottom: 1px solid #d5e2ef;
            padding: 24px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0, 56, 101, 0.06);
        }}

        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
            flex-wrap: wrap;
        }}

        .header-title {{
            display: flex;
            align-items: center;
            gap: 16px;
            flex: 0 1 auto;
        }}

        .logo {{
            max-width: 80px;
            height: auto;
        }}

        .header-text h1 {{
            font-size: 1.8rem;
            color: #005cb9;
            margin: 0;
        }}

        .header-text p {{
            color: #34495e;
            font-size: 0.9rem;
            margin: 0;
        }}

        .controls {{
            display: flex;
            gap: 16px;
            flex: 0 1 auto;
            flex-wrap: wrap;
        }}

        .search-input, .pipeline-select {{
            padding: 10px 16px;
            border: 1px solid #d5e2ef;
            border-radius: 8px;
            font-size: 1rem;
            font-family: Arial, Helvetica, sans-serif;
        }}

        .search-input {{
            min-width: 250px;
            flex: 1;
        }}

        .search-input:focus, .pipeline-select:focus {{
            outline: none;
            border-color: #005cb9;
            box-shadow: 0 0 0 3px rgba(0, 92, 185, 0.1);
        }}

        .pipeline-select {{
            min-width: 180px;
        }}

        main {{
            padding: 40px 24px;
        }}

        .pipeline-section {{
            margin-bottom: 60px;
        }}

        .pipeline-section h2 {{
            font-size: 1.8rem;
            color: #005cb9;
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 2px solid #d9ecff;
        }}

        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 24px;
        }}

        .model-card {{
            background: white;
            border: 1px solid #d5e2ef;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 56, 101, 0.08);
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            height: 100%;
        }}

        .model-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 28px rgba(0, 56, 101, 0.12);
            border-color: #005cb9;
        }}

        .card-thumbnail {{
            width: 100%;
            aspect-ratio: 16 / 9;
            background: linear-gradient(135deg, #e0eef9 0%, #f3f7fb 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #34495e;
            font-size: 0.9rem;
            text-align: center;
            padding: 16px;
            overflow: hidden;
        }}

        .card-thumbnail img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .card-content {{
            padding: 20px;
            display: flex;
            flex-direction: column;
            flex: 1;
        }}

        .card-content h3 {{
            margin: 0 0 8px;
            font-size: 1.2rem;
            color: #005cb9;
            word-break: break-word;
        }}

        .pipeline-badge {{
            display: inline-block;
            margin-bottom: 12px;
            padding: 4px 8px;
            background: #d9ecff;
            color: #005cb9;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            width: fit-content;
        }}

        .card-description {{
            margin: 0 0 12px;
            color: #34495e;
            font-size: 0.9rem;
            flex: 1;
        }}

        .card-org {{
            color: #7f8c8d;
            font-size: 0.85rem;
            margin-bottom: 12px;
        }}

        .card-link {{
            color: #005cb9;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            transition: color 0.3s ease;
        }}

        .card-link:hover {{
            color: #003d84;
        }}

        .hidden {{
            display: none !important;
        }}

        .no-results {{
            text-align: center;
            padding: 60px 24px;
            color: #34495e;
        }}

        .no-results p {{
            font-size: 1.1rem;
            margin: 16px 0;
        }}

        footer {{
            text-align: center;
            padding: 24px;
            border-top: 1px solid #d5e2ef;
            color: #7f8c8d;
            font-size: 0.9rem;
            background: white;
        }}

        footer a {{
            color: #005cb9;
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            .card-grid {{
                grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                gap: 16px;
            }}

            .header-content {{
                flex-direction: column;
                align-items: flex-start;
            }}

            .controls {{
                width: 100%;
                flex-direction: column;
            }}

            .search-input, .pipeline-select {{
                width: 100%;
            }}

            .header-text h1 {{
                font-size: 1.5rem;
            }}

            main {{
                padding: 24px 16px;
            }}

            .pipeline-section h2 {{
                font-size: 1.5rem;
            }}
        }}

        @media (max-width: 480px) {{
            .card-grid {{
                grid-template-columns: 1fr;
                gap: 12px;
            }}

            .header-text h1 {{
                font-size: 1.3rem;
            }}

            .card-content {{
                padding: 16px;
            }}

            main {{
                padding: 16px 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <header>
            <div class="header-content">
                <div class="header-title">
                    <img src="assets/NOAA_FISHERIES_logoH_web.png" alt="NOAA Fisheries" class="logo">
                    <div class="header-text">
                        <h1>Model Gallery</h1>
                        <p>NOAA Model Card Registry</p>
                    </div>
                </div>
                <div class="controls">
                    <input type="text" id="search" class="search-input" placeholder="Search models..." aria-label="Search models">
                    <select id="pipeline-filter" class="pipeline-select" aria-label="Filter by pipeline type">
                        <option value="">All Pipeline Types</option>
                        {pipeline_options}
                    </select>
                </div>
            </div>
        </header>

        <main id="gallery">
            {sections_html_str}
        </main>

        <footer>
            Generated by <strong>NOAA Model Card Template</strong> | 
            <a href="https://github.com/MichaelAkridge-NOAA/model-card-template">GitHub</a>
        </footer>
    </div>

    <script>
        (function() {{
            const cards = document.querySelectorAll('.model-card');
            const sections = document.querySelectorAll('.pipeline-section');
            const searchInput = document.getElementById('search');
            const pipelineFilter = document.getElementById('pipeline-filter');
            const gallery = document.getElementById('gallery');

            function filterCards() {{
                const query = searchInput.value.toLowerCase().trim();
                const selectedPipeline = pipelineFilter.value;
                let visibleSections = 0;
                let totalVisibleCards = 0;

                sections.forEach(section => {{
                    const sectionPipeline = section.dataset.pipeline;
                    let visibleCardsInSection = 0;

                    const sectionCards = section.querySelectorAll('.model-card');
                    sectionCards.forEach(card => {{
                        const searchable = card.dataset.searchable.toLowerCase();
                        const cardPipeline = card.dataset.pipeline;

                        const matchesSearch = query === '' || searchable.includes(query);
                        const matchesPipeline = selectedPipeline === '' || cardPipeline === selectedPipeline;
                        const shouldShow = matchesSearch && matchesPipeline;

                        card.classList.toggle('hidden', !shouldShow);
                        if (shouldShow) {{
                            visibleCardsInSection++;
                            totalVisibleCards++;
                        }}
                    }});

                    const pipelineMatches = selectedPipeline === '' || sectionPipeline === selectedPipeline;
                    const shouldShowSection = visibleCardsInSection > 0 && pipelineMatches;
                    section.classList.toggle('hidden', !shouldShowSection);
                    if (shouldShowSection) {{
                        visibleSections++;
                    }}
                }});

                // Show "no results" message if needed
                if (totalVisibleCards === 0 && (query !== '' || selectedPipeline !== '')) {{
                    showNoResults();
                }} else {{
                    hideNoResults();
                }}
            }}

            function showNoResults() {{
                if (document.getElementById('no-results')) return;
                const noResults = document.createElement('div');
                noResults.id = 'no-results';
                noResults.className = 'no-results';
                noResults.innerHTML = '<p>😕 No models match your search</p><p>Try adjusting your filters or search terms.</p>';
                gallery.appendChild(noResults);
            }}

            function hideNoResults() {{
                const noResults = document.getElementById('no-results');
                if (noResults) {{
                    noResults.remove();
                }}
            }}

            searchInput.addEventListener('keyup', filterCards);
            searchInput.addEventListener('change', filterCards);
            pipelineFilter.addEventListener('change', filterCards);

            // Initial render
            filterCards();
        }})();
    </script>
</body>
</html>
"""
    
    return html


def _generate_card_html(card: Dict) -> str:
    """
    Generate HTML for a single card.
    
    Args:
        card: Card object
        
    Returns:
        HTML string for the card
    """
    model_id = escape_html(card.get("model_id", ""))
    model_name = escape_html(card.get("model_name", ""))
    description = escape_html(card.get("description", ""))
    organization = escape_html(card.get("organization", ""))
    pipeline_type = escape_html(card.get("pipeline_type", ""))
    thumbnail_url = card.get("thumbnail_url", "")
    card_url = card.get("card_url", "")
    
    # Build searchable string (model name, description, organization)
    searchable = f"{model_name} {description} {organization}"
    searchable_escaped = escape_html(searchable)
    
    # Build thumbnail HTML
    if thumbnail_url:
        thumbnail_html = f'<img src="{escape_html(thumbnail_url)}" alt="{model_name}" loading="lazy">'
    else:
        thumbnail_html = f'<div style="display: flex; flex-direction: column; justify-content: center; text-align: center; height: 100%;"><strong>{model_name}</strong><small style="color: #7f8c8d;">{organization}</small></div>'
    
    return f'''<div class="model-card" data-model-id="{model_id}" data-pipeline="{pipeline_type}" data-searchable="{searchable_escaped}">
                <div class="card-thumbnail">
                    {thumbnail_html}
                </div>
                <div class="card-content">
                    <h3>{model_name}</h3>
                    <span class="pipeline-badge">{_format_pipeline_name(pipeline_type)}</span>
                    <p class="card-description">{description}</p>
                    <p class="card-org">Organization: {organization}</p>
                    <a href="{escape_html(card_url)}" class="card-link">View Full Card →</a>
                </div>
            </div>'''


def _format_pipeline_name(pipeline_type: str) -> str:
    """
    Format pipeline type for display (e.g., 'object-detection' -> 'Object Detection').
    
    Args:
        pipeline_type: Snake-case pipeline type string
        
    Returns:
        Title-case formatted string
    """
    return ' '.join(word.capitalize() for word in pipeline_type.split('-'))


def main():
    """Command-line interface for gallery generator."""
    parser = argparse.ArgumentParser(
        description="Generate static HTML gallery from model card registry"
    )
    parser.add_argument(
        "--registry",
        default="gallery/cards.json",
        help="Path to cards.json registry (default: gallery/cards.json)"
    )
    parser.add_argument(
        "--output",
        default="gallery/index.html",
        help="Path to output index.html (default: gallery/index.html)"
    )
    
    args = parser.parse_args()
    
    success, message, card_count = generate_gallery_html(args.registry, args.output)
    
    print(message, file=sys.stdout if success else sys.stderr)
    
    if not success:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
