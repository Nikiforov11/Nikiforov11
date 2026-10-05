"""Turn the tool registry into function declarations the LLM understands.

Pydantic already produces a JSON Schema for each input model. We clean it
before sending it:
  * nested models live under "$defs" and are referenced with "$ref";
    we inline them so the schema is self-contained and simple,
  * "title" fields are dropped: they repeat the property name and cost tokens.

The result is provider-neutral JSON Schema. `core/llm.py` wraps it in
Gemini's types, so the schema the model sees is the *same* schema
`run_tool` validates against. They can't drift apart.
"""
from __future__ import annotations

import copy
from typing import Any

from tools.registry import TOOLS, ToolSpec

DROP_KEYS = {"title"}


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            resolved = _inline_refs(copy.deepcopy(defs[name]), defs)
            # Keep sibling keys such as a field-level "description".
            extra = {k: v for k, v in node.items() if k != "$ref"}
            return {**resolved, **_inline_refs(extra, defs)}
        cleaned = {}
        for key, value in node.items():
            if key in DROP_KEYS or key == "$defs":
                continue
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {name: _inline_refs(prop, defs)
                                for name, prop in value.items()}
            else:
                cleaned[key] = _inline_refs(value, defs)
        return cleaned
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return _inline_refs(schema, schema.get("$defs", {}))


def tool_declaration(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters": clean_schema(spec.input_model.model_json_schema()),
    }


def all_declarations() -> list[dict[str, Any]]:
    return [tool_declaration(spec) for spec in TOOLS.values()]
