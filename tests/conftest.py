"""Shared test helpers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIMPLE_CSV = ROOT / "examples" / "simple" / "items.csv"
SIMPLE_MAP = ROOT / "examples" / "simple" / "items.map.json"
FOUR_LEVEL_CSV = ROOT / "examples" / "four-level" / "items.csv"
FOUR_LEVEL_MAP = ROOT / "examples" / "four-level" / "items.map.json"
TOASTER_CSV = ROOT / "examples" / "toaster-bom" / "items.csv"
TOASTER_MAP = ROOT / "examples" / "toaster-bom" / "items.map.json"


class ScriptedPrompt:
    """PromptIO that returns queued answers."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.messages: list[str] = []

    def ask(self, prompt: str) -> str:
        """Return the next scripted answer."""
        if not self._answers:
            raise AssertionError(f"No scripted answer left for: {prompt}")
        return self._answers.pop(0)

    def tell(self, message: str) -> None:
        """Record a message written to the user."""
        self.messages.append(message)
