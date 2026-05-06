from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from model_card_data import Metric, ModelCardData


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

    sections = [
        CardSection(
            title="Model Summary",
            blocks=[
                *(
                    [TextBlock(text=model_card_data.generated_summary, format="markdown")]
                    if model_card_data.generated_summary
                    else []
                ),
                TextBlock(text=model_card_data.overview),
                _optional_image(
                    model_card_data.assets.detection_example,
                    "Example detection",
                    "Example detection on underwater footage",
                ),
            ],
        ),
        CardSection(
            title="Model Performance",
            blocks=[
                MetricTableBlock(metrics=model_card_data.metrics),
                _optional_image(
                    model_card_data.assets.pr_curve,
                    "Precision recall curve",
                    "Precision-recall curve",
                ),
            ],
        ),
        CardSection(
            title="Usage Guide",
            blocks=[
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
                BulletListBlock(
                    title="Confidence Threshold Settings",
                    items=[
                        f"{threshold.threshold}: {threshold.description}"
                        for threshold in model_card_data.confidence_thresholds
                    ],
                ),
            ],
        ),
    ]

    if model_card_data.intended_use:
        sections.insert(
            1,
            CardSection(
                title="Intended Use",
                blocks=[TextBlock(text=model_card_data.intended_use, format="markdown")],
            ),
        )

    if model_card_data.training_details:
        sections.insert(
            3,
            CardSection(
                title="Training Details",
                blocks=[TextBlock(text=model_card_data.training_details, format="markdown")],
            ),
        )

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
