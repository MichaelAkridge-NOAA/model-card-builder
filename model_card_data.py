from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
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
        "pipelines": {"object-detection"},
    },
    "mAP50-95": {
        "patterns": [
            r"mAP50-95(?:\s*\([^)]+\))?[\s:]+([0-9.]+)",
            r"mAP[@\s]*0\.5[:\-]0\.95[\s:]+([0-9.]+)",
        ],
        "meaning": "Mean Average Precision averaged from IoU 0.50 to 0.95",
        "pipelines": {"object-detection"},
    },
    "Precision": {
        "patterns": [r"[Pp]recision(?:\s*\([^)]+\))?[\s:]+([0-9.]+)"],
        "meaning": "Share of detections that are correct",
        "pipelines": {"object-detection", "image-classification", "default"},
    },
    "Recall": {
        "patterns": [r"[Rr]ecall(?:\s*\([^)]+\))?[\s:]+([0-9.]+)"],
        "meaning": "Share of all labeled items the model finds",
        "pipelines": {"object-detection", "image-classification", "default"},
    },
    "F1": {
        "patterns": [r"\bF1(?:\s+[Ss]core)?[\s:]+([0-9.]+)"],
        "meaning": "Balanced summary of precision and recall",
        "pipelines": {"object-detection", "image-classification", "default"},
    },
    "Accuracy": {
        "patterns": [r"\bAccuracy[\s:]+([0-9.]+)%?"],
        "meaning": "Share of predictions that match the true label",
        "pipelines": {"image-classification"},
    },
    "Balanced Accuracy": {
        "patterns": [r"\bBalanced Accuracy[\s:]+([0-9.]+)%?"],
        "meaning": "Average recall across classes",
        "pipelines": {"image-classification"},
    },
    "Top-1 Accuracy": {
        "patterns": [r"\bTop-1 Accuracy[\s:]+([0-9.]+)%?"],
        "meaning": "Share of samples whose top prediction is correct",
        "pipelines": {"image-classification"},
    },
    "Top-5 Accuracy": {
        "patterns": [r"\bTop-5 Accuracy[\s:]+([0-9.]+)%?"],
        "meaning": "Share of samples whose correct label appears in the top five predictions",
        "pipelines": {"image-classification"},
    },
    "Macro F1": {
        "patterns": [r"\bMacro F1[\s:]+([0-9.]+)%?"],
        "meaning": "Average F1 score across classes",
        "pipelines": {"image-classification"},
    },
    "Macro Precision": {
        "patterns": [r"\bMacro Precision[\s:]+([0-9.]+)%?"],
        "meaning": "Average precision across classes",
        "pipelines": {"image-classification"},
    },
    "Macro Recall": {
        "patterns": [r"\bMacro Recall[\s:]+([0-9.]+)%?"],
        "meaning": "Average recall across classes",
        "pipelines": {"image-classification"},
    },
}

SECTION_ALIASES = {
    "overview": ["model overview", "overview", "model details", "summary"],
    "intended_use": ["models intended use", "intended use", "use cases"],
    "limitations": ["limitations", "additional notes", "ethical considerations"],
    "deployment": ["deployment", "how to use the model", "how to use"],
    "dataset": ["dataset", "dataset annotations", "dataset composition", "data"],
    "training_configuration": ["training configuration", "results metrics", "results metrics", "training", "training validation results", "results and metrics"],
}

PIPELINE_IMAGE_HINTS = {
    "object-detection": {
        "primary_visual": ("example", "prediction", "detection"),
        "performance_visual": ("precision-recall curve", "pr curve", "boxpr_curve", "precision recall", "results"),
    },
    "image-classification": {
        "primary_visual": ("radar", "confusion matrix", "visualization", "performance"),
        "performance_visual": ("confusion matrix", "results", "training curves", "radar"),
    },
    "default": {
        "primary_visual": ("example", "visualization", "sample", "prediction"),
        "performance_visual": ("performance", "results", "curve", "confusion"),
    },
}

SUMMARY_QUALITY_METADATA_PREFIXES = ("language:", "base_model:", "tags:", "pipeline_tag:", "library_name:")


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
    detection_example: Optional[str] = None
    pr_curve: Optional[str] = None


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
    assessment: dict[str, Any] = field(default_factory=dict)
    recovery_actions: list[str] = field(default_factory=list)


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


def parse_metrics(text: Optional[str], pipeline_tag: str = "default") -> list[Metric]:
    if not isinstance(text, str):
        return []

    metrics: dict[str, Metric] = {}
    normalized_pipeline = pipeline_tag or "default"

    for name, definition in METRIC_DEFINITIONS.items():
        allowed_pipelines = definition.get("pipelines", {"default"})
        if normalized_pipeline not in allowed_pipelines and "default" not in allowed_pipelines:
            continue

        value = _extract_metric_value(text, definition["patterns"])
        if value is not None:
            metrics[name] = Metric(name=name, value=value, meaning=definition["meaning"])

    for table_metric in _extract_metrics_from_tables(text, normalized_pipeline):
        metrics.setdefault(table_metric.name, table_metric)

    return list(metrics.values())


def infer_pipeline_tag(source: Any) -> str:
    if isinstance(source, ModelCardData):
        return (
            str(source.metadata.get("Model Type", "")).strip()
            or str(source.model_details.architecture).strip()
            or "default"
        )
    if isinstance(source, Mapping):
        return _first_non_empty(source.get("pipeline_tag"), source.get("Model Type")) or "default"
    return "default"


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
    pipeline_tag = _infer_pipeline_tag(api_data, readme_context.frontmatter)

    overview = _choose_overview(readme_context, card_data)
    intended_use = _choose_section(readme_context.sections, "intended_use")
    limitations = _trim_section(_choose_section(readme_context.sections, "limitations"), ["#### Disclaimer"])
    deployment = _choose_section(readme_context.sections, "deployment")
    training_details = _combine_sections(
        _trim_section(_choose_section(readme_context.sections, "dataset"), ["## Model Performance", "# Metrics"]),
        _trim_section(_choose_section(readme_context.sections, "training_configuration"), ["### Visualizations", "### Training and Validation Losses"]),
    )

    metric_source = "\n\n".join(part for part in [readme_context.body, _card_data_as_text(card_data)] if part)
    metrics = parse_metrics(metric_source, pipeline_tag=pipeline_tag)
    last_modified = _normalize_release_date(api_data.get("lastModified"))

    metadata = _build_metadata(api_data, readme_context.frontmatter, pipeline_tag)
    model_card_data = ModelCardData(
        model_name=str(api_data.get("modelId", readme_context.title or repo_id)),
        model_details=ModelDetails(
            version=str(api_data.get("sha", "latest")),
            release_date=last_modified,
            architecture=_extract_architecture(readme_context, api_data),
            input_size=_extract_input_size(readme_context, api_data),
            training_data=_extract_training_data(readme_context, api_data),
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
        assets=_build_asset_paths(repo_id, readme_context, pipeline_tag),
        recovery_actions=["deterministic-extraction"],
    )
    return _with_assessment(model_card_data)


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


def assess_model_card_data(model_card_data: ModelCardData) -> dict[str, Any]:
    pipeline_tag = infer_pipeline_tag(model_card_data)
    overview_quality = _assess_overview_quality(model_card_data.overview)
    missing_sections = [
        field_name
        for field_name, value in {
            "generated_summary": model_card_data.generated_summary,
            "intended_use": model_card_data.intended_use,
            "limitations": model_card_data.limitations,
            "deployment": model_card_data.deployment,
            "training_details": model_card_data.training_details,
        }.items()
        if not str(value or "").strip()
    ]

    recovery_targets = []
    if overview_quality in {"missing", "metadata_only"}:
        recovery_targets.append("overview")
    if not model_card_data.metrics:
        recovery_targets.append("metrics")
    if not model_card_data.assets.detection_example:
        recovery_targets.append("primary_visual")
    if not model_card_data.assets.pr_curve:
        recovery_targets.append("performance_visual")
    recovery_targets.extend(field_name for field_name in missing_sections if field_name not in recovery_targets)

    return {
        "pipeline_tag": pipeline_tag,
        "overview_quality": overview_quality,
        "has_metrics": bool(model_card_data.metrics),
        "metric_count": len(model_card_data.metrics),
        "has_primary_visual": bool(model_card_data.assets.detection_example),
        "has_performance_visual": bool(model_card_data.assets.pr_curve),
        "missing_sections": missing_sections,
        "recovery_targets": recovery_targets,
        "needs_targeted_recovery": bool(recovery_targets),
    }


def merge_generated_summary(
    model_card_data: ModelCardData,
    summary_payload: Mapping[str, Any],
) -> ModelCardData:
    merged_metrics = list(model_card_data.metrics)
    if not merged_metrics:
        merged_metrics = _metrics_from_summary_payload(summary_payload)

    updated = replace(
        model_card_data,
        intended_use=_prefer_existing(model_card_data.intended_use, summary_payload.get("intended_use")),
        limitations=_prefer_existing(model_card_data.limitations, summary_payload.get("limitations")),
        deployment=_prefer_existing(model_card_data.deployment, summary_payload.get("deployment")),
        training_details=_prefer_existing(model_card_data.training_details, summary_payload.get("training_details")),
        generated_summary=_prefer_existing(model_card_data.generated_summary, summary_payload.get("generated_summary")),
        metrics=merged_metrics or model_card_data.metrics,
        recovery_actions=model_card_data.recovery_actions + ["summary-merged"],
    )
    return _with_assessment(updated)


def apply_targeted_recovery(
    model_card_data: ModelCardData,
    repo_id: str,
    readme_content: str,
    recovery_payload: Mapping[str, Any],
) -> ModelCardData:
    readme_context = _parse_readme_context(repo_id, readme_content)
    metrics = list(model_card_data.metrics) or _metrics_from_summary_payload(recovery_payload)

    primary_hints = [str(item).strip() for item in recovery_payload.get("primary_visual_hints", []) if str(item).strip()]
    performance_hints = [str(item).strip() for item in recovery_payload.get("performance_visual_hints", []) if str(item).strip()]

    primary_visual = model_card_data.assets.detection_example or _choose_image_by_hints(readme_context.images, primary_hints)
    performance_visual = model_card_data.assets.pr_curve or _choose_image_by_hints(
        readme_context.images,
        performance_hints,
        exclude=primary_visual,
    )

    if not primary_visual:
        primary_visual = _choose_visual_fallback(readme_context.images, infer_pipeline_tag(model_card_data), role="primary")
    if not performance_visual:
        performance_visual = _choose_visual_fallback(
            readme_context.images,
            infer_pipeline_tag(model_card_data),
            role="performance",
            exclude=primary_visual,
        )

    updated = replace(
        model_card_data,
        generated_summary=_prefer_existing(model_card_data.generated_summary, recovery_payload.get("generated_summary")),
        metrics=metrics,
        assets=AssetPaths(
            logo=model_card_data.assets.logo,
            detection_example=primary_visual,
            pr_curve=performance_visual,
        ),
        recovery_actions=model_card_data.recovery_actions + ["targeted-recovery"],
    )
    return _with_assessment(updated)


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

    return ReadmeContext(
        frontmatter=frontmatter,
        body=body,
        sections=_extract_markdown_sections(body),
        images=_extract_readme_images(body, repo_id),
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
    for alt_text, path in re.findall(r"!\[(.*?)\]\((.*?)\)", body):
        images.append(ReadmeImage(alt_text=alt_text.strip(), url=_resolve_hf_asset_url(repo_id, path)))
    for path in re.findall(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", body):
        images.append(ReadmeImage(alt_text="README image", url=_resolve_hf_asset_url(repo_id, path)))
    return images


def _choose_overview(readme_context: ReadmeContext, card_data: Any) -> str:
    readme_overview = _choose_section(readme_context.sections, "overview")
    if readme_overview:
        return readme_overview

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

    intro_lines = []
    for line in body.splitlines():
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<img"):
            continue
        intro_lines.append(stripped)
    return _strip_media("\n".join(intro_lines))


def _build_metadata(api_data: Mapping[str, Any], frontmatter: Mapping[str, Any], pipeline_tag: str) -> dict[str, str]:
    metadata = {
        "Model Type": _first_non_empty(api_data.get("pipeline_tag"), frontmatter.get("pipeline_tag"), pipeline_tag),
        "License": _first_non_empty(api_data.get("license"), frontmatter.get("license")),
        "Downloads": str(api_data.get("downloads", 0)),
        "Library": _value_as_text(frontmatter.get("library_name")),
        "Base Model": _value_as_text(frontmatter.get("base_model")),
        "Datasets": _value_as_text(frontmatter.get("datasets")),
        "Tags": _value_as_text(frontmatter.get("tags")),
    }
    return {key: value for key, value in metadata.items() if value}


def _build_asset_paths(repo_id: str, readme_context: ReadmeContext, pipeline_tag: str) -> AssetPaths:
    primary_visual = None
    performance_visual = None

    widget = readme_context.frontmatter.get("widget", [])
    if isinstance(widget, list):
        for item in widget:
            if isinstance(item, dict) and item.get("src"):
                primary_visual = _resolve_hf_asset_url(repo_id, str(item["src"]))
                break

    if not primary_visual:
        primary_visual = _choose_visual_fallback(readme_context.images, pipeline_tag, role="primary")

    performance_visual = _choose_visual_fallback(
        readme_context.images,
        pipeline_tag,
        role="performance",
        exclude=primary_visual,
    )

    return AssetPaths(
        logo=AssetPaths.logo,
        detection_example=primary_visual,
        pr_curve=performance_visual,
    )


def _choose_visual_fallback(
    images: list[ReadmeImage],
    pipeline_tag: str,
    role: str,
    exclude: Optional[str] = None,
) -> Optional[str]:
    hints = PIPELINE_IMAGE_HINTS.get(pipeline_tag, PIPELINE_IMAGE_HINTS["default"])
    url = _choose_image(images, hints[f"{role}_visual"], exclude=exclude)
    if url:
        return url
    return _choose_image(images, PIPELINE_IMAGE_HINTS["default"][f"{role}_visual"], exclude=exclude)


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

    match = re.search(r"[*_`]*Image Size[*_`]*\s*:\s*([0-9]+\s*(?:x|×)\s*[0-9]+|[0-9]+)", readme_context.body, re.IGNORECASE)
    if match:
        return re.sub(r"\s+", "", match.group(1)).replace("×", "x")
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


def _infer_pipeline_tag(api_data: Mapping[str, Any], frontmatter: Mapping[str, Any]) -> str:
    return _first_non_empty(api_data.get("pipeline_tag"), frontmatter.get("pipeline_tag")) or "default"


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

    metrics = [
        Metric(name=item["name"], value=float(item["value"]), meaning=item["meaning"])
        for item in payload.get("metrics", [])
    ]

    thresholds = [
        ThresholdSetting(threshold=item["threshold"], description=item["description"])
        for item in payload.get("confidence_thresholds", [])
    ] or list(DEFAULT_THRESHOLDS)

    return _with_assessment(
        ModelCardData(
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
                logo=assets.get("logo", AssetPaths.logo),
                detection_example=assets.get("detection_example"),
                pr_curve=assets.get("pr_curve"),
            ),
            assessment=dict(payload.get("assessment", {})),
            recovery_actions=[str(item) for item in payload.get("recovery_actions", [])],
        )
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

    return _with_assessment(
        ModelCardData(
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
            metadata={
                "Model Type": str(sections.get("Model Type", "")),
                "Task": str(sections.get("Task", "")),
                "License": str(sections.get("License", "")),
                "Downloads": str(sections.get("Downloads", 0)),
            },
            assets=AssetPaths(),
            recovery_actions=["legacy-load"],
        )
    )


def _with_assessment(model_card_data: ModelCardData) -> ModelCardData:
    return replace(model_card_data, assessment=assess_model_card_data(model_card_data))


def _extract_metric_value(text: str, patterns: list[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        for group in match.groups():
            if group is not None:
                return _parse_numeric_value(group)
    return None


def _extract_metrics_from_tables(text: str, pipeline_tag: str) -> list[Metric]:
    metrics: list[Metric] = []
    table_lines: list[str] = []

    def flush_table() -> None:
        nonlocal metrics, table_lines
        if len(table_lines) < 3:
            table_lines = []
            return

        headers = [_clean_table_cell(cell) for cell in table_lines[0].strip().strip("|").split("|")]
        if len(headers) < 2:
            table_lines = []
            return
        if _normalize_heading(headers[0]) != "metric":
            table_lines = []
            return

        for row in table_lines[2:]:
            cells = [_clean_table_cell(cell) for cell in row.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            name = _normalize_metric_name(cells[0])
            value = _parse_numeric_value(cells[1])
            if value is None:
                continue
            metrics.append(Metric(name=name, value=value, meaning=_metric_meaning(name, pipeline_tag)))
        table_lines = []

    for line in text.splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line)
            continue
        flush_table()
    flush_table()

    unique: dict[str, Metric] = {}
    for metric in metrics:
        unique.setdefault(metric.name, metric)
    return list(unique.values())


def _assess_overview_quality(overview: str) -> str:
    text = str(overview or "").strip()
    if not text:
        return "missing"
    if any(text.startswith(prefix) for prefix in SUMMARY_QUALITY_METADATA_PREFIXES):
        return "metadata_only"
    if text.count("\n-") >= 5 and text.count(":") >= 5 and "http" not in text:
        return "metadata_only"
    if len(text) < 80:
        return "weak"
    return "rich"


def _clean_table_cell(value: str) -> str:
    return re.sub(r"[*`_]", "", value).strip()


def _normalize_metric_name(value: str) -> str:
    cleaned = _clean_table_cell(value)
    aliases = {
        "best top 1 accuracy": "Top-1 Accuracy",
        "best top 5 accuracy": "Top-5 Accuracy",
        "top 5 accuracy": "Top-5 Accuracy",
        "top 1 accuracy": "Top-1 Accuracy",
        "balanced accuracy": "Balanced Accuracy",
        "macro f1": "Macro F1",
        "macro precision": "Macro Precision",
        "macro recall": "Macro Recall",
        "accuracy": "Accuracy",
    }
    return aliases.get(_normalize_heading(cleaned), cleaned)


def _metric_meaning(name: str, pipeline_tag: str) -> str:
    if name in METRIC_DEFINITIONS:
        return METRIC_DEFINITIONS[name]["meaning"]
    if pipeline_tag == "image-classification":
        return "Image-classification evaluation metric"
    if pipeline_tag == "object-detection":
        return "Detection evaluation metric"
    return "Model evaluation metric"


def _parse_numeric_value(value: str) -> Optional[float]:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value))
    if not match:
        return None
    return float(match.group(1))


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


def _choose_image(images: list[ReadmeImage], hints: tuple[str, ...], exclude: Optional[str] = None) -> Optional[str]:
    for image in images:
        if exclude and image.url == exclude:
            continue
        haystack = f"{image.alt_text} {image.url}".lower()
        if any(hint in haystack for hint in hints):
            return image.url
    return None


def _choose_image_by_hints(images: list[ReadmeImage], hints: list[str], exclude: Optional[str] = None) -> Optional[str]:
    for image in images:
        if exclude and image.url == exclude:
            continue
        haystack = f"{image.alt_text} {image.url}".lower()
        if any(hint.lower() in haystack for hint in hints):
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
        meaning = str(item.get("meaning", "")).strip() or _metric_meaning(name, "default")
        parsed_value = _parse_numeric_value(str(item.get("value", "")))
        if not name or parsed_value is None:
            continue
        metrics.append(Metric(name=name, value=parsed_value, meaning=meaning))
    return metrics
