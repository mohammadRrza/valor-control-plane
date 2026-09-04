"""Provider-neutral usage facts attached to an Invocation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InvocationUsage:
    input_units: int | None
    output_units: int | None
    total_units: int | None

    def __post_init__(self) -> None:
        for name, value in (
            ("input_units", self.input_units),
            ("output_units", self.output_units),
            ("total_units", self.total_units),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise TypeError(f"Invocation usage {name} must be an integer when present.")
            if value is not None and value < 0:
                raise ValueError(f"Invocation usage {name} must not be negative.")
        if self.total_units is not None:
            if self.input_units is not None and self.total_units < self.input_units:
                raise ValueError("Total usage must not be less than input usage.")
            if self.output_units is not None and self.total_units < self.output_units:
                raise ValueError("Total usage must not be less than output usage.")
