from __future__ import annotations

import base64
import html
import mimetypes
import os
from typing import Optional

import markdown

from python.model_card_document import (
    BulletListBlock,
    CardDocument,
    CardSection,
    ImageBlock,
    KeyValueListBlock,
    MetricTableBlock,
    TextBlock,
)


NOAA_THEME_CSS = """
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  background: #f3f7fb;
  color: #1a1a1a;
}

.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}

.masthead {
  text-align: center;
  margin-bottom: 24px;
}

.template-badge {
  display: inline-block;
  margin-bottom: 12px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #d9ecff;
  color: #005cb9;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.title {
  margin: 0 0 8px;
  color: #005cb9;
  font-size: 2.4rem;
}

.subtitle {
  margin: 0;
  color: #34495e;
  font-size: 1rem;
}

.logo {
  display: block;
  max-width: 240px;
  margin: 0 auto 18px;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
}

.card-section {
  background: #ffffff;
  border: 1px solid #d5e2ef;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 24px rgba(0, 56, 101, 0.08);
}

.card-section h2 {
  margin-top: 0;
  color: #005cb9;
}

.block-title {
  margin: 0 0 10px;
  font-size: 1rem;
}

.metric-table {
  width: 100%;
  border-collapse: collapse;
}

.metric-table th,
.metric-table td {
  padding: 10px;
  border-bottom: 1px solid #d5e2ef;
  text-align: left;
  vertical-align: top;
}

.metric-table th {
  color: #005cb9;
}

.metric-value {
  font-weight: 700;
}

.image-block {
  margin-top: 16px;
}

.image-block img {
  width: 100%;
  border-radius: 12px;
  border: 1px solid #d5e2ef;
}

.image-block figcaption {
  margin-top: 8px;
  font-size: 0.9rem;
  color: #4f6578;
}

.key-value-list,
.bullet-list {
  margin: 0;
  padding-left: 18px;
}

.key-value-list li,
.bullet-list li {
  margin-bottom: 8px;
}

.footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #d5e2ef;
  color: #4f6578;
  font-size: 0.95rem;
  text-align: center;
}
"""

BRANDED_THEME_CSS_PATH = "assets/branded_theme.css"
BRANDED_TEMPLATE_PATH = "assets/branded_template.html"


def render_card_document(document: CardDocument, output_path: str) -> None:
    rendered = render_card_document_to_string(document, output_path)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(rendered)


def _load_asset_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def render_card_document_to_string(
    document: CardDocument,
    output_path: Optional[str] = None,
) -> str:
    logo_html = ""
    logo_path = _asset_url(document.logo_path, output_path)
    if logo_path:
        logo_html = f'<img class="logo" src="{logo_path}" alt="Organization logo">'

    if document.theme == "noaa":
        theme_css = NOAA_THEME_CSS
    elif document.theme == "branded":
        theme_css = _load_asset_file(BRANDED_THEME_CSS_PATH)
    else:
        theme_css = ""

    if document.template == "branded":
        return _render_branded_template(document, logo_html, theme_css, output_path)

    sections_html = "\n".join(_render_section(section, output_path) for section in document.sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document.title)}</title>
  <style>{theme_css}</style>
</head>
<body class="theme-{html.escape(document.theme)}">
  <main class="page template-{html.escape(document.template)}">
    <header class="masthead">
      {logo_html}
      <div class="template-badge">{html.escape(document.template)} template</div>
      <h1 class="title">{html.escape(document.title)}</h1>
      <p class="subtitle">{html.escape(document.subtitle)}</p>
    </header>
    <section class="section-grid">
      {sections_html}
    </section>
    <footer class="footer">{html.escape(document.footer)}</footer>
  </main>
</body>
</html>
"""


def _render_branded_template(
    document: CardDocument,
    logo_html: str,
    theme_css: str,
    output_path: Optional[str],
) -> str:
    # Branded template expects exactly 4 sections in a specific order:
    # 0: Overview, 1: Performance, 2: Technical, 3: How to Use
    # We wrap them in specific containers for the grid layout.

    overview_section = _render_branded_section(document.sections[0], output_path, "overview")
    performance_section = _render_branded_section(document.sections[1], output_path, "performance")
    technical_section = _render_branded_section(document.sections[2], output_path, "technical")
    usage_section = _render_branded_section(document.sections[3], output_path, "usage")

    template_html = _load_asset_file(BRANDED_TEMPLATE_PATH)
    if not template_html:
        # Fallback if template file is missing
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document.title)}</title>
  <style>{theme_css}</style>
</head>
<body class="theme-{html.escape(document.theme)}">
  <main class="page template-branded">
    <header class="masthead">
      {logo_html}
      <h1 class="title">{html.escape(document.title)}</h1>
      <p class="subtitle">{html.escape(document.subtitle)}</p>
    </header>
    <div class="section-grid">
      {overview_section}
      {performance_section}
      <div class="section-row-bottom">
        {technical_section}
        {usage_section}
      </div>
    </div>
    <footer class="footer">{html.escape(document.footer)}</footer>
  </main>
</body>
</html>
"""

    # Inject template variables
    replacements = {
        "{{ title }}": html.escape(document.title),
        "{{ logo_html }}": logo_html,
        "{{ subtitle }}": html.escape(document.subtitle),
        "{{ theme_css }}": theme_css,
        "{{ theme }}": html.escape(document.theme),
        "{{ overview_section }}": overview_section,
        "{{ performance_section }}": performance_section,
        "{{ technical_section }}": technical_section,
        "{{ usage_section }}": usage_section,
        "{{ footer }}": html.escape(document.footer),
    }

    for placeholder, value in replacements.items():
        template_html = template_html.replace(placeholder, value)

    return template_html


def _render_branded_section(section: CardSection, output_path: Optional[str], section_type: str) -> str:
    # For "overview" section in branded template, we split blocks into left (metadata) and right (image)
    if section_type == "overview":
        left_blocks = "\n".join(_render_block(block, output_path) for block in section.blocks if not isinstance(block, ImageBlock))
        right_blocks = "\n".join(_render_block(block, output_path) for block in section.blocks if isinstance(block, ImageBlock))
        content = f"""
        <div class="section-body">
            <div class="column-left">{left_blocks}</div>
            <div class="column-right">{right_blocks}</div>
        </div>
        """
    else:
        content = "\n".join(_render_block(block, output_path) for block in section.blocks)

    return f"""
<article class="card-section type-{section_type}">
  <h2>{html.escape(section.title)}</h2>
  {content}
</article>
"""
def _render_section(section: CardSection, output_path: Optional[str]) -> str:
    blocks = "\n".join(_render_block(block, output_path) for block in section.blocks)
    return f"""
<article class="card-section">
  <h2>{html.escape(section.title)}</h2>
  {blocks}
</article>
"""


def _render_block(block: object, output_path: Optional[str]) -> str:
    if isinstance(block, TextBlock):
        return _render_text_block(block)
    if isinstance(block, MetricTableBlock):
        return _render_metric_table(block)
    if isinstance(block, ImageBlock):
        return _render_image_block(block, output_path)
    if isinstance(block, KeyValueListBlock):
        return _render_key_value_list(block)
    if isinstance(block, BulletListBlock):
        return _render_bullet_list(block)
    raise TypeError(f"Unsupported block type: {type(block)!r}")


def _render_text_block(block: TextBlock) -> str:
    if block.format == "markdown":
        content = markdown.markdown(block.text, extensions=["extra", "sane_lists"])
    else:
        content = f"<p>{html.escape(block.text)}</p>"
    return f'<div class="text-block">{content}</div>'


def _render_metric_table(block: MetricTableBlock) -> str:
    if not block.metrics:
        return "<p>No metrics were found in the source model card.</p>"

    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(metric.name)}</td>
          <td class="metric-value">{metric.value:.3f}</td>
          <td>{html.escape(metric.meaning)}</td>
        </tr>
        """
        for metric in block.metrics
    )
    return f"""
<table class="metric-table">
  <thead>
    <tr>
      <th>Metric</th>
      <th>Value</th>
      <th>Meaning</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
"""


def _render_image_block(block: ImageBlock, output_path: Optional[str]) -> str:
    asset_url = _asset_url(block.path, output_path)
    if not asset_url:
        return ""

    caption_html = f"<figcaption>{html.escape(block.caption)}</figcaption>" if block.caption else ""
    return f"""
<figure class="image-block">
  <img src="{asset_url}" alt="{html.escape(block.alt_text)}">
  {caption_html}
</figure>
"""


def _render_key_value_list(block: KeyValueListBlock) -> str:
    items = "\n".join(
        f"<li><strong>{html.escape(label)}:</strong> {html.escape(value)}</li>"
        for label, value in block.items
    )
    return f"""
<section>
  <h3 class="block-title">{html.escape(block.title)}</h3>
  <ul class="key-value-list">
    {items}
  </ul>
</section>
"""


def _render_bullet_list(block: BulletListBlock) -> str:
    items = "\n".join(f"<li>{html.escape(item)}</li>" for item in block.items)
    return f"""
<section>
  <h3 class="block-title">{html.escape(block.title)}</h3>
  <ul class="bullet-list">
    {items}
  </ul>
</section>
"""


def _asset_url(path: Optional[str], output_path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return html.escape(path, quote=True)

    normalized = _normalize_local_path(path)
    inline_asset = _inline_local_asset(normalized, output_path)
    if inline_asset:
        return inline_asset

    if output_path and os.path.isabs(normalized):
        output_dir = os.path.dirname(os.path.abspath(output_path))
        normalized = os.path.relpath(normalized, output_dir)
    return html.escape(normalized.replace("\\", "/"), quote=True)


def _inline_local_asset(path: str, output_path: Optional[str]) -> Optional[str]:
    asset_path = path
    if not os.path.isabs(asset_path):
        # Prefer resolving relative to CWD (project root) so assets committed
        # alongside the repository are found regardless of the output location.
        cwd_candidate = os.path.join(os.getcwd(), asset_path)
        if os.path.exists(cwd_candidate):
            asset_path = cwd_candidate
        elif output_path:
            asset_path = os.path.join(os.path.dirname(os.path.abspath(output_path)), asset_path)
        else:
            asset_path = cwd_candidate

    if not os.path.exists(asset_path):
        return None

    mime_type, _ = mimetypes.guess_type(asset_path)
    if not mime_type or not mime_type.startswith("image/"):
        return None

    with open(asset_path, "rb") as asset_file:
        encoded = base64.b64encode(asset_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_local_path(path: str) -> str:
    normalized = path.replace("\\", os.sep).replace("/", os.sep)
    return os.path.normpath(normalized)
