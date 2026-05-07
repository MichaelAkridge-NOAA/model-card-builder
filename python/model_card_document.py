from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from python.model_card_data import Metric, ModelCardData, infer_pipeline_tag


SUPPORTED_TEMPLATES = {"standard"}
SUPPORTED_THEMES = {"noaa"}


@dataclass(frozen=True)
class TextBlock:
    text: str
    format: str = "markdown"


@dataclass(frozen=True)
class ImageBlock:
    path: str
    alt_text: str
    caption: str = ""


@dataclass(frozen=True)
class MetricTableBlock:
    metrics: list[Metric]


@dataclass(frozen=True)
class KeyValueListBlock:
    title: str
    items: list[tuple[str, str]]


@dataclass(frozen=True)
class BulletListBlock:
    title: str
    items: list[str]


Block = Union[TextBlock, ImageBlock, MetricTableBlock, KeyValueListBlock, BulletListBlock]


@dataclass(frozen=True)
class CardSection:
    title: str
    blocks: list[Block]


@dataclass(frozen=True)
class CardDocument:
    title: str
    subtitle: str
    template: str
    theme: str
    logo_path: Optional[str]
    sections: list[CardSection]
    footer: str


def build_card_document(
    model_card_data: ModelCardData,
    template: str = "standard",
    theme: str = "noaa",
) -> CardDocument:
    if template not in SUPPORTED_TEMPLATES:
        raise ValueError(f"Unsupported template '{template}'.")
    if theme not in SUPPORTED_THEMES:
        raise ValueError(f"Unsupported theme '{theme}'.")

    pipeline_tag = infer_pipeline_tag(model_card_data)
    summary_blocks = []
    if model_card_data.generated_summary:
        summary_blocks.append(TextBlock(text=model_card_data.generated_summary, format="markdown"))
    if _should_render_overview(model_card_data):
        summary_blocks.append(TextBlock(text=model_card_data.overview))
    primary_image_caption, primary_image_alt = _primary_visual_labels(pipeline_tag)
    primary_image = _optional_image(
        model_card_data.assets.detection_example,
        primary_image_alt,
        primary_image_caption,
    )
    if primary_image is not None:
        summary_blocks.append(primary_image)

    sections = []
    if summary_blocks:
        sections.append(CardSection(title="Model Summary", blocks=summary_blocks))

    if model_card_data.intended_use:
        sections.append(
            CardSection(
                title="Intended Use",
                blocks=[TextBlock(text=model_card_data.intended_use, format="markdown")],
            )
        )

    performance_blocks = []
    if model_card_data.metrics:
        performance_blocks.append(MetricTableBlock(metrics=model_card_data.metrics))
    performance_caption, performance_alt = _performance_visual_labels(pipeline_tag)
    performance_image = _optional_image(
        model_card_data.assets.pr_curve,
        performance_alt,
        performance_caption,
    )
    if performance_image is not None:
        performance_blocks.append(performance_image)
    if performance_blocks:
        sections.append(CardSection(title="Model Performance", blocks=performance_blocks))

    if model_card_data.training_details:
        sections.append(
            CardSection(
                title="Training Details",
                blocks=[TextBlock(text=model_card_data.training_details, format="markdown")],
            )
        )

    usage_blocks = [
        *(
            [TextBlock(text=model_card_data.deployment, format="markdown")]
            if model_card_data.deployment
            else []
        ),
        KeyValueListBlock(
            title="Technical Details",
            items=[
                ("Architecture", model_card_data.model_details.architecture),
                ("Input Size", model_card_data.model_details.input_size),
                ("Training Data", model_card_data.model_details.training_data),
            ],
        ),
    ]
    if _supports_confidence_thresholds(pipeline_tag):
        usage_blocks.append(
            BulletListBlock(
                title="Confidence Threshold Settings",
                items=[
                    f"{threshold.threshold}: {threshold.description}"
                    for threshold in model_card_data.confidence_thresholds
                ],
            )
        )
    sections.append(CardSection(title="Usage Guide", blocks=usage_blocks))

    if model_card_data.limitations:
        sections.append(
            CardSection(
                title="Limitations",
                blocks=[TextBlock(text=model_card_data.limitations, format="markdown")],
            )
        )

    metadata_items = [(key, value) for key, value in model_card_data.metadata.items() if value]
    if metadata_items:
        sections.append(
            CardSection(
                title="Model Metadata",
                blocks=[KeyValueListBlock(title="Repository Metadata", items=metadata_items)],
            )
        )

    filtered_sections = [
        CardSection(
            title=section.title,
            blocks=[block for block in section.blocks if block is not None],
        )
        for section in sections
    ]

    subtitle = (
        f"Version {model_card_data.model_details.version} | "
        f"{model_card_data.model_details.release_date}"
    )
    footer = (
        f"{model_card_data.footer_info.organization} | "
        f"Contact: {model_card_data.footer_info.contact_email} | "
        f"Version {model_card_data.footer_info.version} | "
        f"{model_card_data.footer_info.year}"
    )

    return CardDocument(
        title=model_card_data.model_name,
        subtitle=subtitle,
        template=template,
        theme=theme,
        logo_path=model_card_data.assets.logo,
        sections=filtered_sections,
        footer=footer,
    )


def _optional_image(path: Optional[str], alt_text: str, caption: str) -> Optional[ImageBlock]:
    if not path:
        return None
    return ImageBlock(path=path, alt_text=alt_text, caption=caption)


def _should_render_overview(model_card_data: ModelCardData) -> bool:
    if not model_card_data.overview:
        return False
    if model_card_data.generated_summary and model_card_data.assessment.get("overview_quality") == "metadata_only":
        return False
    return True


def _supports_confidence_thresholds(pipeline_tag: str) -> bool:
    return pipeline_tag == "object-detection"


def _primary_visual_labels(pipeline_tag: str) -> tuple[str, str]:
    if pipeline_tag == "image-classification":
        return ("Representative model visualization", "Representative model visualization")
    return ("Example detection on underwater footage", "Example detection")


def _performance_visual_labels(pipeline_tag: str) -> tuple[str, str]:
    if pipeline_tag == "image-classification":
        return ("Performance visualization", "Performance visualization")
    return ("Precision-recall curve", "Precision recall curve")
