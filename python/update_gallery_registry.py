#!/usr/bin/env python
"""
Registry management for the GitHub Pages model card gallery.

This module provides functions to maintain a centralized JSON index of all generated
model cards, including validation and duplicate detection.
"""

import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "gallery" / "cards.json"
REQUIRED_FIELDS = {"model_id", "model_name", "model_url", "pipeline_type", "organization", "date_added"}


def add_card_to_registry(
    model_id: str,
    model_name: str,
    model_url: str,
    pipeline_type: str,
    organization: str,
    description: str,
    thumbnail_url: Optional[str] = None,
    registry_path: Path = REGISTRY_PATH,
) -> bool:
    """
    Add a new model card to the registry.
    
    Args:
        model_id: Unique identifier for the model
        model_name: Human-readable model name
        model_url: HuggingFace model URL
        pipeline_type: ML task type (e.g., 'object-detection', 'image-classification')
        organization: HuggingFace organization name
        description: Brief 1-2 sentence overview
        thumbnail_url: Optional thumbnail URL or relative path
        registry_path: Path to cards.json registry file
        
    Returns:
        True if card was added, False if duplicate already exists
        
    Raises:
        ValueError: If any required field is invalid
    """
    # Validate inputs
    if not model_id or not isinstance(model_id, str):
        raise ValueError("model_id must be a non-empty string")
    if not model_name or not isinstance(model_name, str):
        raise ValueError("model_name must be a non-empty string")
    if not model_url or not isinstance(model_url, str):
        raise ValueError("model_url must be a non-empty string")
    if not pipeline_type or not isinstance(pipeline_type, str):
        raise ValueError("pipeline_type must be a non-empty string")
    if not organization or not isinstance(organization, str):
        raise ValueError("organization must be a non-empty string")
    if not description or not isinstance(description, str):
        raise ValueError("description must be a non-empty string")
    
    # Load existing registry or create empty structure
    if registry_path.exists() and registry_path.stat().st_size > 0:
        with open(registry_path, "r") as f:
            data = json.load(f)
    else:
        data = {
            "_schema_version": "1.0",
            "_schema_description": "Registry of all generated model cards.",
            "cards": []
        }
    
    # Ensure cards list exists
    if "cards" not in data:
        data["cards"] = []
    
    # Check for duplicates
    for card in data["cards"]:
        if card.get("model_id") == model_id:
            return False  # Duplicate exists
    
    # Create new card entry
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    new_card = {
        "model_id": model_id,
        "model_name": model_name,
        "model_url": model_url,
        "card_url": f"cards/{model_id}.html",
        "pipeline_type": pipeline_type,
        "date_added": now,
        "description": description,
        "organization": organization,
    }
    
    if thumbnail_url:
        new_card["thumbnail_url"] = thumbnail_url
    
    # Add card and sort by date_added (newest first)
    data["cards"].append(new_card)
    data["cards"].sort(key=lambda x: x["date_added"], reverse=True)
    
    # Write back to file with pretty printing
    with open(registry_path, "w") as f:
        json.dump(data, f, indent=2)
    
    return True


def validate_registry(registry_path: Path = REGISTRY_PATH) -> tuple[bool, List[str]]:
    """
    Validate the registry file for data integrity.
    
    Args:
        registry_path: Path to cards.json registry file
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    if not registry_path.exists() or registry_path.stat().st_size == 0:
        # Empty registry is valid
        return True, []
    
    try:
        with open(registry_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {str(e)}"]
    
    if "cards" not in data:
        errors.append("Missing 'cards' array in registry")
        return False, errors
    
    if not isinstance(data["cards"], list):
        errors.append("'cards' must be an array")
        return False, errors
    
    seen_ids = set()
    for i, card in enumerate(data["cards"]):
        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in card:
                errors.append(f"Card {i}: missing required field '{field}'")
            elif not isinstance(card[field], str) or not card[field]:
                errors.append(f"Card {i}: field '{field}' must be non-empty string")
        
        # Check model_id uniqueness
        model_id = card.get("model_id", "")
        if model_id in seen_ids:
            errors.append(f"Card {i}: duplicate model_id '{model_id}'")
        seen_ids.add(model_id)
        
        # Validate ISO 8601 timestamp
        if "date_added" in card:
            try:
                datetime.fromisoformat(card["date_added"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                errors.append(f"Card {i}: invalid ISO 8601 timestamp '{card.get('date_added')}'")
        
        # Validate URLs are non-empty strings
        if "model_url" in card and (not card["model_url"] or not isinstance(card["model_url"], str)):
            errors.append(f"Card {i}: model_url must be non-empty string")
    
    return len(errors) == 0, errors


def main():
    """Command-line entry point for registry management."""
    parser = argparse.ArgumentParser(
        description="Manage the model card gallery registry"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Add card command
    add_parser = subparsers.add_parser("add", help="Add a new card to the registry")
    add_parser.add_argument("--model-id", required=True, help="Unique model identifier")
    add_parser.add_argument("--model-name", required=True, help="Human-readable model name")
    add_parser.add_argument("--model-url", required=True, help="HuggingFace model URL")
    add_parser.add_argument("--pipeline-type", required=True, help="ML task type")
    add_parser.add_argument("--organization", required=True, help="HuggingFace organization")
    add_parser.add_argument("--description", required=True, help="Brief model description")
    add_parser.add_argument("--thumbnail-url", help="Optional thumbnail URL")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate the registry")
    
    args = parser.parse_args()
    
    if args.command == "add":
        try:
            added = add_card_to_registry(
                model_id=args.model_id,
                model_name=args.model_name,
                model_url=args.model_url,
                pipeline_type=args.pipeline_type,
                organization=args.organization,
                description=args.description,
                thumbnail_url=args.thumbnail_url,
            )
            if added:
                print(f"Added card: {args.model_id}", file=sys.stdout)
                return 0
            else:
                print(f"Error: Card with model_id '{args.model_id}' already exists", file=sys.stderr)
                return 1
        except ValueError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1
    
    elif args.command == "validate":
        is_valid, errors = validate_registry()
        if is_valid:
            print("Registry is valid", file=sys.stdout)
            return 0
        else:
            for error in errors:
                print(f"Error: {error}", file=sys.stderr)
            return 1
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
