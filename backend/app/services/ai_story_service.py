"""Zero-hallucination Change Story: model may only cite numbers in engine_payload."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings

STORY_KEYS = ("headline", "why_it_matters", "what_changed_summary", "action_context")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

SYSTEM_PROMPT = """You are Groww Signal's Change Story writer.

ZERO-HALLUCINATION POLICY (strict):
- Use ONLY numbers that appear in the provided engine_payload JSON.
- Do not invent prices, percents, volumes, z-scores, MCI values, RSI, dates, or any other figures.
- Do not round to a number that is not already present in the payload.
- If a fact is missing from the payload, omit it. Never guess.
- Do not mention companies, events, or catalysts that are not implied by the payload fields.

Return a JSON object with exactly these keys:
{
  "headline": string,
  "why_it_matters": string,
  "what_changed_summary": array of strings,
  "action_context": string
}
"""


def _add_number_token(allowed: set[str], value: float) -> None:
    as_float = float(value)
    allowed.add(f"{as_float:.10g}")
    allowed.add(str(as_float))
    if as_float.is_integer():
        allowed.add(str(int(as_float)))
    for digits in (1, 2, 4):
        allowed.add(f"{as_float:.{digits}f}")
        allowed.add(f"{as_float:.{digits}f}".rstrip("0").rstrip("."))


def allowed_number_tokens(payload: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            _add_number_token(allowed, float(node))
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return {token for token in allowed if token and token != "-"}


def extract_numbers(text: str) -> list[str]:
    return NUMBER_RE.findall(text or "")


def numbers_are_grounded(story: dict[str, Any], payload: dict[str, Any]) -> bool:
    allowed = allowed_number_tokens(payload)
    blob = json.dumps(story, ensure_ascii=False)
    return all(token in allowed for token in extract_numbers(blob))


def _deterministic_story(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol", "UNKNOWN"))
    mci = payload.get("mci")
    priority = payload.get("priority")
    price = payload.get("price")
    previous_price = payload.get("previous_price")
    price_delta = payload.get("price_delta")
    price_delta_pct = payload.get("price_delta_pct")
    volume = payload.get("volume")
    previous_volume = payload.get("previous_volume")
    volume_delta_pct = payload.get("volume_delta_pct")
    z_volume = payload.get("z_volume")
    z_price = payload.get("z_price")
    sector_relative_delta = payload.get("sector_relative_delta")

    headline = f"{symbol} MCI {mci} ({priority})"
    why = (
        f"{symbol} moved from {previous_price} to {price} "
        f"({price_delta}, {price_delta_pct} percent) since the last session snapshot."
    )
    changed = [
        f"Price delta {price_delta} ({price_delta_pct} percent).",
        f"Volume {volume} vs {previous_volume} ({volume_delta_pct} percent).",
        f"Z_V {z_volume}, Z_P {z_price}, sector relative delta {sector_relative_delta}.",
        f"MCI {mci} maps to {priority}.",
    ]
    action = (
        f"Use {priority} as the attention rank only. "
        f"All figures are from the engine payload; no catalyst was added."
    )
    return {
        "headline": headline,
        "why_it_matters": why,
        "what_changed_summary": changed,
        "action_context": action,
    }


def _coerce_story(raw: dict[str, Any]) -> dict[str, Any]:
    summary = raw.get("what_changed_summary", [])
    if isinstance(summary, str):
        summary = [summary]
    if not isinstance(summary, list):
        summary = [str(summary)]
    return {
        "headline": str(raw.get("headline", "")),
        "why_it_matters": str(raw.get("why_it_matters", "")),
        "what_changed_summary": [str(item) for item in summary],
        "action_context": str(raw.get("action_context", "")),
    }


def _call_openai(payload: dict[str, Any]) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"engine_payload": payload}, ensure_ascii=False),
            },
        ],
    )
    content = completion.choices[0].message.content or "{}"
    return _coerce_story(json.loads(content))


def _call_gemini(payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps({"engine_payload": payload}, ensure_ascii=False),
                    }
                ],
            }
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"gemini request failed: {exc}") from exc
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _coerce_story(json.loads(text))


def generate_change_story(engine_payload: dict[str, Any]) -> dict[str, Any]:
    grounded = _deterministic_story(engine_payload)
    source = "deterministic"
    try:
        if settings.openai_api_key:
            candidate = _call_openai(engine_payload)
            source = "openai"
        elif settings.gemini_api_key:
            candidate = _call_gemini(engine_payload)
            source = "gemini"
        else:
            candidate = grounded
    except Exception:
        candidate = grounded
        source = "deterministic_fallback"

    if not numbers_are_grounded(candidate, engine_payload):
        candidate = grounded
        source = "grounding_repair"

    candidate["grounding"] = {
        "source": source,
        "numbers_from_payload_only": True,
    }
    return candidate
