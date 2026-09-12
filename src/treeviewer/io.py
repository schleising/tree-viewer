"""Prompt I/O ports so mapping can run without a live TTY."""

from typing import Protocol, TextIO


class PromptIO(Protocol):
    """Ask questions and emit prompt-side messages."""

    def ask(self, prompt: str) -> str:
        """Return one line of user input for `prompt`."""
        ...

    def tell(self, message: str) -> None:
        """Write a message to the user."""
        ...


class StreamPrompt:
    """PromptIO backed by text streams.

    Attributes:
        input_stream: Source of answers, usually `sys.stdin`.
        output_stream: Destination for prompts and messages.
    """

    def __init__(self, input_stream: TextIO, output_stream: TextIO) -> None:
        self._input = input_stream
        self._output = output_stream

    def ask(self, prompt: str) -> str:
        """Write `prompt` and read a line."""
        self._output.write(prompt)
        self._output.flush()
        return self._input.readline().rstrip("\n")

    def tell(self, message: str) -> None:
        """Write `message` followed by a newline."""
        self._output.write(f"{message}\n")
        self._output.flush()
