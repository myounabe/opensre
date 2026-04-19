"""Base tool interface for opensre integrations.

All tools must inherit from BaseTool and implement the required methods
as defined in .cursor/rules/tools.mdc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Encapsulates the result of a tool execution."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


class BaseTool(ABC):
    """Abstract base class for all opensre tools.

    Subclasses must implement:
      - my_tool_name (class attribute)
      - is_available()
      - extract_params()
      - run()

    Example::

        class MyTool(BaseTool):
            my_tool_name = "my_tool"

            def is_available(self) -> bool:
                return shutil.which("mytool") is not None

            def extract_params(self, raw: dict) -> dict:
                return {"target": raw["target"]}

            def run(self, params: dict) -> ToolResult:
                ...
    """

    #: Unique snake_case identifier for this tool (required by tools.mdc)
    my_tool_name: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "my_tool_name", ""):
            raise TypeError(
                f"{cls.__name__} must define a non-empty 'my_tool_name' class attribute."
            )

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this tool's dependencies are present in the environment."""

    @abstractmethod
    def extract_params(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate and extract tool-specific parameters from a raw input dict.

        Args:
            raw: Unvalidated input, typically from a graph node payload.

        Returns:
            A clean dict of parameters ready for :meth:`run`.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """

    @abstractmethod
    def run(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given parameters.

        Args:
            params: Validated parameters produced by :meth:`extract_params`.

        Returns:
            A :class:`ToolResult` describing the outcome.
        """

    def __call__(self, raw: dict[str, Any]) -> ToolResult:
        """Convenience entry-point: validate availability, extract params, then run."""
        if not self.is_available():
            return ToolResult(
                success=False,
                error=f"Tool '{self.my_tool_name}' is not available in this environment.",
            )
        try:
            params = self.extract_params(raw)
        except (ValueError, KeyError) as exc:
            return ToolResult(success=False, error=f"Parameter error: {exc}")
        # NOTE: catching broad Exception here so unexpected runtime errors from tools
        # are surfaced as ToolResult failures rather than crashing the caller.
        try:
            return self.run(params)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"Unexpected error: {exc}")
