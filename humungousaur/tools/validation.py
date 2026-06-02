from __future__ import annotations

from typing import Any


class ToolInputValidationError(ValueError):
    pass


def validate_tool_input(value: Any, schema: dict[str, Any], path: str = "tool_input") -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        _validate_type(value, str(expected_type), path)
    allowed_values = schema.get("enum")
    if isinstance(allowed_values, list) and value not in allowed_values:
        allowed = ", ".join(str(item) for item in allowed_values)
        raise ToolInputValidationError(f"{path} must be one of: {allowed}.")

    if expected_type == "object" or isinstance(value, dict):
        if not isinstance(value, dict):
            raise ToolInputValidationError(f"{path} must be an object.")
        _validate_object(value, schema, path)
    elif expected_type == "array" or isinstance(value, list):
        if not isinstance(value, list):
            raise ToolInputValidationError(f"{path} must be an array.")
        _validate_array(value, schema, path)
    elif expected_type in {"integer", "number"}:
        _validate_number_bounds(value, schema, path)


def _validate_object(value: dict[str, Any], schema: dict[str, Any], path: str) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict):
        properties = {}
    if not isinstance(required, list):
        required = []

    for key in required:
        if key not in value:
            raise ToolInputValidationError(f"{path}.{key} is required.")

    additional = schema.get("additionalProperties", True)
    for key, item in value.items():
        child_path = f"{path}.{key}"
        if key in properties:
            validate_tool_input(item, properties[key], child_path)
            continue
        if additional is False:
            allowed = ", ".join(sorted(properties)) or "none"
            raise ToolInputValidationError(f"{child_path} is not allowed. Allowed fields: {allowed}.")
        if isinstance(additional, dict):
            validate_tool_input(item, additional, child_path)


def _validate_array(value: list[Any], schema: dict[str, Any], path: str) -> None:
    min_items = schema.get("minItems")
    max_items = schema.get("maxItems")
    if isinstance(min_items, int) and len(value) < min_items:
        raise ToolInputValidationError(f"{path} must contain at least {min_items} item(s).")
    if isinstance(max_items, int) and len(value) > max_items:
        raise ToolInputValidationError(f"{path} must contain at most {max_items} item(s).")
    item_schema = schema.get("items")
    if isinstance(item_schema, dict):
        for index, item in enumerate(value):
            validate_tool_input(item, item_schema, f"{path}[{index}]")


def _validate_type(value: Any, expected_type: str, path: str) -> None:
    if expected_type == "object" and not isinstance(value, dict):
        raise ToolInputValidationError(f"{path} must be an object.")
    if expected_type == "array" and not isinstance(value, list):
        raise ToolInputValidationError(f"{path} must be an array.")
    if expected_type == "string" and not isinstance(value, str):
        raise ToolInputValidationError(f"{path} must be a string.")
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ToolInputValidationError(f"{path} must be an integer.")
    if expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ToolInputValidationError(f"{path} must be a number.")
    if expected_type == "boolean" and not isinstance(value, bool):
        raise ToolInputValidationError(f"{path} must be a boolean.")


def _validate_number_bounds(value: Any, schema: dict[str, Any], path: str) -> None:
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    if isinstance(minimum, (int, float)) and value < minimum:
        raise ToolInputValidationError(f"{path} must be at least {minimum}.")
    if isinstance(maximum, (int, float)) and value > maximum:
        raise ToolInputValidationError(f"{path} must be at most {maximum}.")
