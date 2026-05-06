from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
import os
import re
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import requests
import yaml


METRIC_DEFINITIONS = {
    "mAP50": {
        "patterns": [
            r"mAP50(?![-0-9])(?:\s*\([^)]+\))?[\s:]+([0-9.]+)",
            r"mAP[@\s]*0\.5[\s:]+([0-9.]+)",
        ],
        "meaning": "Mean Average Precision at 0.5 IoU",
    },
    "mAP50-95": {
        "patterns": [
            r"mAP50-95(?:\s*\([^)]+\))?[\s:]+([0-9.]+)",
            r"mAP[@\s]*0\.5[:\-]0\.95[\s:]+([0-9.]+)",
        ],
        "meaning": "Mean Average Precision averaged from IoU 0.50 to 0.95",
    },
    "Precision": {
        "patterns": [r"[Pp]recision(?:\s*\([^)]+\))?[\s:]+([0-9.]+)"],
        "meaning": "Share of detections that are real fish",
    },
    "Recall": {
        "patterns": [r"[Rr]ecall(?:\s*\([^)]+\))?[\s:]+([0-9.]+)"],
        "meaning": "Share of all fish that are found",
    },
    "F1": {
        "patterns": [r"\bF1(?:\s+[Ss]core)?[\s:]+([0-9.]+)"],
        "meaning": "Balanced summary of precision and recall",
    },
}

SECTION_ALIASES = {
    "overview": ["overview", "model details", "summary"],
    "intended_use": ["models intended use", "intended use", "use cases"],
    "limitations": ["limitations", "additional notes"],
    "deployment": ["deployment", "how to use the model"],
    "dataset": ["dataset", "dataset composition", "data"],
    "training_configuration": ["training configuration", "training", "training validation results"],
}

IMAGE_HINTS = {
    "pr_curve": ("precision-recall curve", "pr curve", "boxpr_curve", "precision recall"),
    "detection_example": ("example", "prediction", "detection"),
}


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    meaning: str


@dataclass(frozen=True)
class ThresholdSetting:
    threshold: str
    description: str


@dataclass(frozen=True)
class FooterInfo:
    organization: str
    contact_email: str
    version: str
    year: str


@dataclass(frozen=True)
class AssetPaths:
    logo: Optional[str] = "assets\\NOAA_FISHERIES_logoH_web.png"
    detection_example: Optional[str] = "assets\\example_detection.png"
    pr_curve: Optional[str] = "assets\\example_PR_curve.png"


@dataclass(frozen=True)
class ModelDetails:
    version: str
    release_date: str
    architecture: str
    input_size: str
    training_data: str


@dataclass(frozen=True)
class ModelCardData:
    model_name: str
    model_details: ModelDetails
    overview: str
    intended_use: str
    limitations: str
    deployment: str
    training_details: str
    generated_summary: str
    metrics: list[Metric]
    confidence_thresholds: list[ThresholdSetting]
    footer_info: FooterInfo
    metadata: dict[str, str]
    assets: AssetPaths


@dataclass(frozen=True)
class ReadmeImage:
    alt_text: str
    url: str


@dataclass(frozen=True)
class ReadmeContext:
    frontmatter: dict[str, Any]
    body: str
    sections: dict[str, str]
    images: list[ReadmeImage]
    title: str


DEFAULT_THRESHOLDS = [
    ThresholdSetting("0.20", "Maximum recall, more false positives"),
    ThresholdSetting("0.50", "Balanced detection (default)"),
    ThresholdSetting("0.80", "High precision, fewer false positives"),
]

DEFAULT_FOOTER = FooterInfo(
    organization="NOAA / CIMAR",
    contact_email="michael.akridge@noaa.gov",
    version="1.0",
    year="2025",
)


def parse_metrics(text: Optional[str]) -> list[Metric]:
    if not isinstance(text, str):
        return []

    metrics: list[Metric] = []
    for name, definition in METRIC_DEFINITIONS.items():
        value = _extract_metric_value(text, definition["patterns"])
        if value is not None:
            metrics.append(Metric(name=name, value=value, meaning=definition["meaning"]))
    return metrics


def extract_repo_id(url_or_id: str) -> str:
    if url_or_id.startswith("http"):
        parsed = urlparse(url_or_id)
        path = parsed.path.strip("/")
        parts = path.split("/")
        if "models" in parts:
            model_index = parts.index("models")
            return "/".join(parts[model_index + 1 :])
        return path
    return url_or_id


def fetch_readme_content(repo_id: str) -> Optional[str]:
    readme_url = f"https://huggingface.co/{repo_id}/raw/main/README.md"
    try:
        response = requests.get(readme_url, timeout=30)
    except requests.RequestException:
        return None
    if response.status_code == 200:
        return response.text
    return None


def fetch_model_card_data(url_or_id: str) -> ModelCardData:
    repo_id = extract_repo_id(url_or_id)
    api_url = f"https://huggingface.co/api/models/{repo_id}"

    try:
        response = requests.get(api_url, timeout=30)
    except requests.RequestException:
        print(f"Warning: Failed to fetch model card from API {api_url}")
        api_data: Mapping[str, Any] = {}
    else:
        if response.status_code != 200:
            print(f"Warning: Failed to fetch model card from API {api_url}")
            api_data = {}
        else:
            api_data = response.json()

    readme_content = fetch_readme_content(repo_id)
    return build_model_card_data(repo_id, api_data, readme_content)


def build_model_card_data(
    repo_id: str,
    api_data: Mapping[str, Any],
    readme_content: Optional[str] = None,
) -> ModelCardData:
    readme_context = _parse_readme_context(repo_id, readme_content)
    card_data = api_data.get("cardData", {})

    overview = _choose_overview(readme_context, card_data)
    intended_use = _choose_section(readme_context.sections, "intended_use")
    limitations = _trim_section(_choose_section(readme_context.sections, "limitations"), ["#### Disclaimer"])
    deployment = _choose_section(readme_context.sections, "deployment")
    training_details = _combine_sections(
        _trim_section(_choose_section(readme_context.sections, "dataset"), ["## Model Performance", "# Metrics"]),
        _trim_section(
            _choose_section(readme_context.sections, "training_configuration"),
            ["### Training and Validation Losses"],
        ),
    )

    metric_source = "\n\n".join(
        part for part in [readme_context.body, _card_data_as_text(card_data)] if part
    )
    metrics = parse_metrics(metric_source)
    last_modified = _normalize_release_date(api_data.get("lastModified"))

    architecture = _extract_architecture(readme_context, api_data)
    input_size = _extract_input_size(readme_context, api_data)
    training_data = _extract_training_data(readme_context, api_data)

    metadata = _build_metadata(api_data, readme_context.frontmatter)
    assets = _build_asset_paths(repo_id, readme_context)

    return ModelCardData(
        model_name=str(api_data.get("modelId", readme_context.title or repo_id)),
        model_details=ModelDetails(
            version=str(api_data.get("sha", "latest")),
            release_date=last_modified,
            architecture=architecture,
            input_size=input_size,
            training_data=training_data,
        ),
        overview=overview or "No overview available.",
        intended_use=intended_use,
        limitations=limitations,
        deployment=deployment,
        training_details=training_details,
        generated_summary="",
        metrics=metrics,
        confidence_thresholds=list(DEFAULT_THRESHOLDS),
        footer_info=DEFAULT_FOOTER,
        metadata=metadata,
        assets=assets,
    )


def model_card_data_to_dict(model_card_data: ModelCardData) -> dict[str, Any]:
    return asdict(model_card_data)


def model_card_data_from_dict(payload: Mapping[str, Any]) -> ModelCardData:
    if "model_name" in payload and "model_details" in payload and "overview" in payload:
        return _from_current_contract(payload)
    if "model_info" in payload and "sections" in payload:
        return _from_legacy_contract(payload)
    raise ValueError("Unsupported model card payload format.")


def save_model_card_data(model_card_data: ModelCardData, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(model_card_data_to_dict(model_card_data), file, indent=2, ensure_ascii=False)


def load_model_card_data(path: str) -> ModelCardData:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    return model_card_data_from_dict(payload)


def merge_generated_summary(
    model_card_data: ModelCardData,
    summary_payload: Mapping[str, Any],
) -> ModelCardData:
    merged_metrics = list(model_card_data.metrics)
    if not merged_metrics:
        merged_metrics = _metrics_from_summary_payload(summary_payload)

    return replace(
        model_card_data,
        intended_use=_prefer_existing(model_card_data.intended_use, summary_payload.get("intended_use")),
        limitations=_prefer_existing(model_card_data.limitations, summary_payload.get("limitations")),
        deployment=_prefer_existing(model_card_data.deployment, summary_payload.get("deployment")),
        training_details=_prefer_existing(
            model_card_data.training_details,
            summary_payload.get("training_details"),
        ),
        generated_summary=str(summary_payload.get("generated_summary", "")).strip(),
        metrics=merged_metrics or model_card_data.metrics,
    )


def with_assets_dir(model_card_data: ModelCardData, assets_dir: Optional[str]) -> ModelCardData:
    if not assets_dir:
        return model_card_data

    def _resolve(asset_path: Optional[str]) -> Optional[str]:
        if not asset_path or asset_path.startswith("http://") or asset_path.startswith("https://"):
            return asset_path
        return os.path.join(assets_dir, os.path.basename(asset_path))

    return replace(
        model_card_data,
        assets=AssetPaths(
            logo=_resolve(model_card_data.assets.logo),
            detection_example=_resolve(model_card_data.assets.detection_example),
            pr_curve=_resolve(model_card_data.assets.pr_curve),
        ),
    )


def _extract_metric_value(text: str, patterns: list[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        for group in match.groups():
            if group is not None:
                return float(group)
    return None


def _parse_readme_context(repo_id: str, readme_content: Optional[str]) -> ReadmeContext:
    if not readme_content:
        return ReadmeContext(frontmatter={}, body="", sections={}, images=[], title="")

    content = readme_content.replace("\r\n", "\n").strip()
    frontmatter: dict[str, Any] = {}
    body = content

    frontmatter_match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if frontmatter_match:
        parsed_frontmatter = yaml.safe_load(frontmatter_match.group(1)) or {}
        if isinstance(parsed_frontmatter, dict):
            frontmatter = parsed_frontmatter
        body = content[frontmatter_match.end() :].strip()

    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    sections = _extract_markdown_sections(body)
    images = _extract_readme_images(body, repo_id)

    return ReadmeContext(
        frontmatter=frontmatter,
        body=body,
        sections=sections,
        images=images,
        title=title,
    )


def _extract_markdown_sections(body: str) -> dict[str, str]:
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(body))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = _normalize_heading(match.group(2))
        start = match.end()
        end = len(body)
        for next_match in matches[index + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        content = body[start:end].strip()
        if content:
            sections[title] = content
    return sections


def _extract_readme_images(body: str, repo_id: str) -> list[ReadmeImage]:
    images: list[ReadmeImage] = []

    markdown_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
    html_pattern = re.compile(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>")

    for alt_text, path in markdown_pattern.findall(body):
        images.append(ReadmeImage(alt_text=alt_text.strip(), url=_resolve_hf_asset_url(repo_id, path)))

    for path in html_pattern.findall(body):
        images.append(ReadmeImage(alt_text="README image", url=_resolve_hf_asset_url(repo_id, path)))

    return images


def _choose_overview(readme_context: ReadmeContext, card_data: Any) -> str:
    readme_overview = _choose_section(readme_context.sections, "overview")
    if readme_overview:
        return _strip_media(readme_overview)

    intro = _extract_intro_text(readme_context.body)
    if intro:
        return intro

    card_text = _card_data_as_text(card_data)
    if card_text:
        return card_text

    return ""


def _choose_section(sections: Mapping[str, str], alias_key: str) -> str:
    for alias in SECTION_ALIASES[alias_key]:
        candidate = sections.get(alias, "")
        if candidate:
            return _strip_media(candidate)
    return ""


def _combine_sections(*sections: str) -> str:
    cleaned: list[str] = []
    for section in sections:
        candidate = _strip_media(section)
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return "\n\n".join(cleaned)


def _trim_section(section: str, markers: list[str]) -> str:
    trimmed = section
    for marker in markers:
        if marker in trimmed:
            trimmed = trimmed.split(marker, 1)[0].strip()
    return trimmed.strip()


def _extract_intro_text(body: str) -> str:
    if not body:
        return ""

    lines = []
    before_first_subheading = []
    for line in body.splitlines():
        if line.startswith("## "):
            break
        before_first_subheading.append(line)

    for line in before_first_subheading:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<img"):
            continue
        lines.append(stripped)

    return _strip_media("\n".join(lines))


def _build_metadata(api_data: Mapping[str, Any], frontmatter: Mapping[str, Any]) -> dict[str, str]:
    metadata = {
        "Model Type": _first_non_empty(api_data.get("pipeline_tag"), frontmatter.get("pipeline_tag")),
        "License": _first_non_empty(api_data.get("license"), frontmatter.get("license")),
        "Downloads": str(api_data.get("downloads", 0)),
        "Library": _value_as_text(frontmatter.get("library_name")),
        "Base Model": _value_as_text(frontmatter.get("base_model")),
        "Datasets": _value_as_text(frontmatter.get("datasets")),
        "Tags": _value_as_text(frontmatter.get("tags")),
    }
    return {key: value for key, value in metadata.items() if value}


def _build_asset_paths(repo_id: str, readme_context: ReadmeContext) -> AssetPaths:
    widget = readme_context.frontmatter.get("widget", [])
    detection_example = None
    if isinstance(widget, list):
        for item in widget:
            if isinstance(item, dict) and item.get("src"):
                detection_example = _resolve_hf_asset_url(repo_id, str(item["src"]))
                break

    if not detection_example:
        detection_example = _choose_image(readme_context.images, IMAGE_HINTS["detection_example"])

    pr_curve = _choose_image(readme_context.images, IMAGE_HINTS["pr_curve"])

    return AssetPaths(
        logo=AssetPaths.logo,
        detection_example=detection_example or AssetPaths.detection_example,
        pr_curve=pr_curve or AssetPaths.pr_curve,
    )


def _extract_architecture(readme_context: ReadmeContext, api_data: Mapping[str, Any]) -> str:
    candidates = [
        _extract_labeled_value(readme_context.body, "Model Architecture"),
        _value_as_text(readme_context.frontmatter.get("base_model")),
        str(api_data.get("pipeline_tag", "")),
    ]
    return _first_non_empty(*candidates) or "Not specified"


def _extract_input_size(readme_context: ReadmeContext, api_data: Mapping[str, Any]) -> str:
    config_image_size = api_data.get("config", {}).get("image_size")
    if config_image_size:
        return str(config_image_size)

    match = re.search(
        r"[*_`]*Image Size[*_`]*\s*:\s*([0-9]+(?:x[0-9]+)?)",
        readme_context.body,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return "N/A"


def _extract_training_data(readme_context: ReadmeContext, api_data: Mapping[str, Any]) -> str:
    dataset_text = _value_as_text(readme_context.frontmatter.get("datasets"))
    if dataset_text:
        return dataset_text

    dataset_section = _choose_section(readme_context.sections, "dataset")
    if dataset_section:
        first_line = next((line.strip("- ").strip() for line in dataset_section.splitlines() if line.strip()), "")
        if first_line:
            return first_line

    return str(api_data.get("pipeline_tag", "N/A") or "N/A")


def _normalize_release_date(raw_value: Any) -> str:
    if isinstance(raw_value, str) and raw_value:
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def _from_current_contract(payload: Mapping[str, Any]) -> ModelCardData:
    model_details = payload["model_details"]
    footer_info = payload.get("footer_info", {})
    assets = payload.get("assets", {})
    default_assets = AssetPaths()

    metrics = [
        Metric(name=item["name"], value=float(item["value"]), meaning=item["meaning"])
        for item in payload.get("metrics", [])
    ]

    thresholds = [
        ThresholdSetting(threshold=item["threshold"], description=item["description"])
        for item in payload.get("confidence_thresholds", [])
    ] or list(DEFAULT_THRESHOLDS)

    return ModelCardData(
        model_name=str(payload["model_name"]),
        model_details=ModelDetails(
            version=str(model_details.get("version", "latest")),
            release_date=str(model_details.get("release_date", "N/A")),
            architecture=str(model_details.get("architecture", "Not specified")),
            input_size=str(model_details.get("input_size", "N/A")),
            training_data=str(model_details.get("training_data", "N/A")),
        ),
        overview=str(payload.get("overview", "No overview available.")),
        intended_use=str(payload.get("intended_use", "")),
        limitations=str(payload.get("limitations", "")),
        deployment=str(payload.get("deployment", "")),
        training_details=str(payload.get("training_details", "")),
        generated_summary=str(payload.get("generated_summary", "")),
        metrics=metrics,
        confidence_thresholds=thresholds,
        footer_info=FooterInfo(
            organization=str(footer_info.get("organization", DEFAULT_FOOTER.organization)),
            contact_email=str(footer_info.get("contact_email", DEFAULT_FOOTER.contact_email)),
            version=str(footer_info.get("version", DEFAULT_FOOTER.version)),
            year=str(footer_info.get("year", DEFAULT_FOOTER.year)),
        ),
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
        assets=AssetPaths(
            logo=assets.get("logo", default_assets.logo),
            detection_example=assets.get("detection_example", default_assets.detection_example),
            pr_curve=assets.get("pr_curve", default_assets.pr_curve),
        ),
    )


def _from_legacy_contract(payload: Mapping[str, Any]) -> ModelCardData:
    model_info = payload.get("model_info", {})
    sections = payload.get("sections", {})
    overview = str(sections.get("Overview", "No overview available."))
    metrics_payload = model_info.get("metrics", {})

    metrics = [
        Metric(name=name, value=float(value), meaning=METRIC_DEFINITIONS[name]["meaning"])
        for name, value in metrics_payload.items()
        if value is not None and name in METRIC_DEFINITIONS
    ]
    if not metrics:
        metrics = parse_metrics(overview)

    metadata = {
        "Model Type": str(sections.get("Model Type", "")),
        "Task": str(sections.get("Task", "")),
        "License": str(sections.get("License", "")),
        "Downloads": str(sections.get("Downloads", 0)),
    }

    return ModelCardData(
        model_name=str(model_info.get("model_name", "Unnamed Model")),
        model_details=ModelDetails(
            version=str(model_info.get("version", "latest")),
            release_date=str(model_info.get("release_date", "N/A")),
            architecture=str(model_info.get("architecture", "Not specified")),
            input_size=str(model_info.get("input_size", "N/A")),
            training_data=str(model_info.get("training_data", "N/A")),
        ),
        overview=overview,
        intended_use="",
        limitations="",
        deployment="",
        training_details="",
        generated_summary="",
        metrics=metrics,
        confidence_thresholds=list(DEFAULT_THRESHOLDS),
        footer_info=DEFAULT_FOOTER,
        metadata=metadata,
        assets=AssetPaths(),
    )


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _strip_media(text: str) -> str:
    without_images = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    without_html_images = re.sub(r"<img[^>]*>", "", without_images)
    return without_html_images.strip()


def _resolve_hf_asset_url(repo_id: str, path: str) -> str:
    normalized_path = path.strip()
    if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
        return normalized_path

    normalized_path = normalized_path.lstrip("./")
    return f"https://huggingface.co/{repo_id}/resolve/main/{normalized_path}"


def _choose_image(images: list[ReadmeImage], hints: tuple[str, ...]) -> Optional[str]:
    for image in images:
        haystack = f"{image.alt_text} {image.url}".lower()
        if any(hint in haystack for hint in hints):
            return image.url
    return None


def _card_data_as_text(card_data: Any) -> str:
    if isinstance(card_data, str):
        candidate = card_data.strip()
        if candidate and not _looks_like_serialized_mapping(candidate):
            return candidate
        return ""
    if isinstance(card_data, Mapping):
        return yaml.safe_dump(dict(card_data), sort_keys=False).strip()
    return ""


def _looks_like_serialized_mapping(value: str) -> bool:
    return value.startswith("{") and value.endswith("}") and ":" in value


def _extract_labeled_value(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\**\s*:\s*([^\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"[*`_]", "", match.group(1)).strip()


def _value_as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _value_as_text(value).strip()
        if text:
            return text
    return ""


def _prefer_existing(existing_value: str, candidate: Any) -> str:
    existing = str(existing_value or "").strip()
    if existing:
        return existing
    return str(candidate or "").strip()


def _metrics_from_summary_payload(summary_payload: Mapping[str, Any]) -> list[Metric]:
    metrics: list[Metric] = []
    for item in summary_payload.get("key_metrics", []):
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        value = item.get("value")
        if not name or value in (None, ""):
            continue
        try:
            parsed_value = float(value)
        except (TypeError, ValueError):
            continue
        metrics.append(Metric(name=name, value=parsed_value, meaning=meaning))
    return metrics
