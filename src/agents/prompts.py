"""
Agent prompts loader for the vision analysis pipeline.

Prompts are stored in separate .txt files to maintain separation of concerns.
This module loads them at runtime.

CRITICAL: These prompts follow the 4 non-negotiable rules:
1. Nothing is hardcoded
2. Nothing is guessed
3. A rule exists only if observed
4. An unstable rule is rejected
"""

from pathlib import Path
from functools import lru_cache

# Directory containing prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    """Load a prompt from a text file."""
    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    return filepath.read_text(encoding="utf-8").strip()


# Guide Builder prompts
def get_guide_builder_system() -> str:
    """Get the Guide Builder system prompt."""
    return _load_prompt("guide_builder_system.txt")


def get_guide_builder_prompt(token_summary_text: str = "") -> str:
    """Get the Guide Builder user prompt.

    Args:
        token_summary_text: Optional token summary from PDF extraction.
            If provided, replaces {token_summary_section} placeholder.
    """
    template = _load_prompt("guide_builder_user.txt")

    # Build token summary section
    if token_summary_text:
        token_section = f"""
═══════════════════════════════════════════════════════════════════════════════
TEXT TOKENS (from PDF vector layer) — PRIORITY DATA
═══════════════════════════════════════════════════════════════════════════════

The following text tokens were extracted directly from the PDF vector layer.
This data is EXACT and takes priority over visual analysis for text detection.

{token_summary_text}

Use this information to:
1. CONFIRM room_name patterns (uppercase words like CLASSE, CORRIDOR)
2. CONFIRM room_number patterns (2-4 digit numbers near names)
3. IDENTIFY pairing relationship (position: below, right, etc.)
4. IDENTIFY exclude candidates (high-frequency codes like "05" = wall type)

When token data is available, your observations MUST align with it.
"""
    else:
        token_section = ""

    return template.replace("{token_summary_section}", token_section)


# Guide Applier prompts
def get_guide_applier_system() -> str:
    """Get the Guide Applier system prompt."""
    return _load_prompt("guide_applier_system.txt")


def get_guide_applier_prompt() -> str:
    """Get the Guide Applier user prompt template."""
    return _load_prompt("guide_applier_user.txt")


# Self-Validator prompts
def get_self_validator_system() -> str:
    """Get the Self-Validator system prompt."""
    return _load_prompt("self_validator_system.txt")


def get_self_validator_prompt() -> str:
    """Get the Self-Validator user prompt template."""
    return _load_prompt("self_validator_user.txt")


# Guide Consolidator prompts
def get_guide_consolidator_system() -> str:
    """Get the Guide Consolidator system prompt."""
    return _load_prompt("guide_consolidator_system.txt")


def get_guide_consolidator_prompt() -> str:
    """Get the Guide Consolidator user prompt template."""
    return _load_prompt("guide_consolidator_user.txt")
