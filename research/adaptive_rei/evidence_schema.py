"""Ollama output schema for REI evidence graphs; semantic checks live in the parser."""

POLARITY = {"type": "string", "enum": ["yes", "no"]}
DEPENDENCY = {
    "type": "array",
    "prefixItems": [{"type": "integer", "minimum": 1}, POLARITY],
    "minItems": 2,
    "maxItems": 2,
}
ITEM = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "enum": ["yes", "no", "gap", "undercut"]},
        "strength": {"type": "integer", "enum": [1, 2, 3]},
        "quote": {"type": "string"},
        "requires": {"type": "array", "items": DEPENDENCY},
        "target": {"type": "integer", "minimum": 1},
    },
    "required": ["answer", "strength", "quote", "requires"],
    "additionalProperties": False,
}
CLAIM = {
    "type": "object",
    "properties": {
        "claim": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "items": ITEM},
    },
    "required": ["claim", "evidence"],
    "additionalProperties": False,
}
GRAPH = {
    "type": "object",
    "properties": {"claims": {"type": "array", "minItems": 1, "maxItems": 20, "items": CLAIM}},
    "required": ["claims"],
    "additionalProperties": False,
}
