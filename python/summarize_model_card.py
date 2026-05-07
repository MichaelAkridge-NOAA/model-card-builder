from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

# Allow running as `python python/summarize_model_card.py` from repo root.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from python.model_card_data import (
    apply_targeted_recovery,
    assess_model_card_data,
    extract_repo_id,
    fetch_readme_content,
    load_model_card_data,
    merge_generated_summary,
    save_model_card_data,
)


DEFAULT_ENDPOINT = "https://models.github.ai/inference/chat/completions"


def summarize_model_card(
    url_or_id: str,
    data_path: str,
    prompt_path: str,
    recovery_prompt_path: Optional[str] = None,
    endpoint: str = DEFAULT_ENDPOINT,
) -> None:
    model_card_data = load_model_card_data(data_path)
    missing_fields = _missing_narrative_fields(model_card_data)
    repo_id = extract_repo_id(url_or_id)
    readme_content = fetch_readme_content(repo_id)
    if not readme_content:
        raise RuntimeError(f"README.md could not be fetched for {repo_id}.")

    if missing_fields:
        prompt = _load_prompt(prompt_path)
        messages = _render_messages(
            messages=prompt["messages"],
            model_card_markdown=readme_content,
            model_card_data=model_card_data,
            missing_fields=missing_fields,
            assessment=model_card_data.assessment,
        )
        summary_payload = _request_summary_payload(
            model=prompt["model"],
            messages=messages,
            model_parameters=prompt.get("modelParameters", {}),
            endpoint=endpoint,
            retries=1,
        )
        model_card_data = merge_generated_summary(model_card_data, summary_payload)
        save_model_card_data(model_card_data, data_path)
        print("Merged narrative summary fields.")
    else:
        print("No missing narrative fields. Skipping primary summary step.")

    assessment = assess_model_card_data(model_card_data)
    print(json.dumps(assessment, indent=2, ensure_ascii=False))

    if recovery_prompt_path and os.path.exists(recovery_prompt_path) and _needs_targeted_recovery(assessment):
        recovery_prompt = _load_prompt(recovery_prompt_path)
        recovery_messages = _render_messages(
            messages=recovery_prompt["messages"],
            model_card_markdown=readme_content,
            model_card_data=model_card_data,
            missing_fields=assessment["recovery_targets"],
            assessment=assessment,
        )
        recovery_payload = _request_summary_payload(
            model=recovery_prompt["model"],
            messages=recovery_messages,
            model_parameters=recovery_prompt.get("modelParameters", {}),
            endpoint=endpoint,
            retries=1,
        )
        model_card_data = apply_targeted_recovery(model_card_data, repo_id, readme_content, recovery_payload)
        save_model_card_data(model_card_data, data_path)
        print("Applied targeted recovery.")
    else:
        print("No targeted recovery needed.")


def _load_prompt(prompt_path: str) -> dict[str, Any]:
    with open(prompt_path, "r", encoding="utf-8") as file:
        prompt = yaml.safe_load(file)
    if not isinstance(prompt, dict):
        raise ValueError("Prompt file must be a YAML object.")
    return prompt


def _render_messages(
    messages: list[dict[str, Any]],
    model_card_markdown: str,
    model_card_data: Any,
    missing_fields: list[str],
    assessment: dict[str, Any],
) -> list[dict[str, Any]]:
    rendered = []
    existing_data = json.dumps(
        {
            "generated_summary": model_card_data.generated_summary,
            "intended_use": model_card_data.intended_use,
            "limitations": model_card_data.limitations,
            "deployment": model_card_data.deployment,
            "training_details": model_card_data.training_details,
        },
        indent=2,
        ensure_ascii=False,
    )
    assessment_json = json.dumps(assessment, indent=2, ensure_ascii=False)
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            content = (
                content.replace("{{input}}", model_card_markdown)
                .replace("{{existing_data}}", existing_data)
                .replace("{{missing_fields}}", ", ".join(missing_fields))
                .replace("{{assessment}}", assessment_json)
            )
        rendered.append({"role": message["role"], "content": content})
    return rendered


def _call_models_api(
    model: str,
    messages: list[dict[str, Any]],
    model_parameters: dict[str, Any],
    endpoint: str,
) -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN or GH_TOKEN is required to call GitHub Models.")

    payload = {"model": model, "messages": messages}
    payload.update(model_parameters)

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    response_json = response.json()
    return str(response_json["choices"][0]["message"]["content"])


def _request_summary_payload(
    model: str,
    messages: list[dict[str, Any]],
    model_parameters: dict[str, Any],
    endpoint: str,
    retries: int,
) -> dict[str, Any]:
    attempt_messages = list(messages)
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            response_text = _call_models_api(
                model=model,
                messages=attempt_messages,
                model_parameters=model_parameters,
                endpoint=endpoint,
            )
            payload = _parse_summary_payload(response_text)
            return _normalize_summary_payload(payload)
        except (json.JSONDecodeError, ValueError, KeyError) as error:
            last_error = error
            if attempt == retries:
                break
            attempt_messages = attempt_messages + [
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid. "
                        "Return only a valid JSON object with the exact requested keys."
                    ),
                }
            ]

    if last_error is not None:
        raise last_error
    raise RuntimeError("GitHub Models summary request failed without a parseable response.")


def _parse_summary_payload(response_text: str) -> dict[str, Any]:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Summary response must be a JSON object.")
    return payload


def _normalize_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_summary": str(payload.get("generated_summary", "")).strip(),
        "intended_use": str(payload.get("intended_use", "")).strip(),
        "limitations": str(payload.get("limitations", "")).strip(),
        "deployment": str(payload.get("deployment", "")).strip(),
        "training_details": str(payload.get("training_details", "")).strip(),
        "key_metrics": payload.get("key_metrics", []),
        "primary_visual_hints": payload.get("primary_visual_hints", []),
        "performance_visual_hints": payload.get("performance_visual_hints", []),
    }


def _missing_narrative_fields(model_card_data: Any) -> list[str]:
    fields = {
        "generated_summary": model_card_data.generated_summary,
        "intended_use": model_card_data.intended_use,
        "limitations": model_card_data.limitations,
        "deployment": model_card_data.deployment,
        "training_details": model_card_data.training_details,
    }
    return [name for name, value in fields.items() if not str(value or "").strip()]


def _needs_targeted_recovery(assessment: dict[str, Any]) -> bool:
    return bool(assessment.get("needs_targeted_recovery"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a Hugging Face model card with GitHub Models and merge the result into model_data.json."
    )
    parser.add_argument("--url", required=True, help="Hugging Face model URL or org/model repo id")
    parser.add_argument("--data", required=True, help="Path to model_data.json")
    parser.add_argument("--prompt", required=True, help="Path to prompts/summarize.prompt.yaml")
    parser.add_argument("--recovery-prompt", help="Path to targeted recovery prompt")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="GitHub Models inference endpoint")
    args = parser.parse_args()

    summarize_model_card(
        url_or_id=args.url,
        data_path=args.data,
        prompt_path=args.prompt,
        recovery_prompt_path=args.recovery_prompt,
        endpoint=args.endpoint,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
