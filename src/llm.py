"""
Shared model-call helpers for the steps that generate text (briefs, sequences).
One place for the client setup, the structured-output request, and cost arithmetic.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def make_client():
    import anthropic  # imported here so the checks and tests run without the SDK installed

    # Keys that are not tied to one workspace must name the workspace on every request.
    workspace = os.getenv("ANTHROPIC_WORKSPACE_ID")
    return anthropic.Anthropic(default_headers={"anthropic-workspace-id": workspace} if workspace else None)


def generate_json(client, cfg: dict, system: str, prompt: str, schema: dict):
    response = client.beta.messages.create(
        model=cfg["model"],
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": cfg["effort"], "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with {response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.usage, response.model


def cost_usd(usage, price_per_mtok: dict) -> float:
    return round(
        (usage.input_tokens * price_per_mtok["input"] + usage.output_tokens * price_per_mtok["output"]) / 1_000_000, 4
    )


def load_prompt(vertical_dir: Path, filename: str) -> str:
    """Read a prompt file, filling {seller_context} from the vertical's seller_context.md."""
    seller = (vertical_dir / "seller_context.md").read_text().strip()
    return (vertical_dir / filename).read_text().replace("{seller_context}", seller)
