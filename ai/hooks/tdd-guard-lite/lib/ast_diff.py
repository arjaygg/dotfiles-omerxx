"""
AST structural diff — Option 4 enforcement.

Uses tree-sitter to extract top-level named symbols from before/after
versions of a file. Classifies the change as PURE_REFACTOR or
BEHAVIORAL_ADDITION (new function/class/method not present before).

Requires: pip install tree-sitter tree-sitter-languages
Falls back gracefully to ALLOW if tree-sitter is unavailable.

Supported languages: typescript, javascript, python, go
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set


@dataclass
class AstDiffResult:
    is_pure_refactor: bool
    new_symbols: Set[str] = field(default_factory=set)
    removed_symbols: Set[str] = field(default_factory=set)
    reason: str = ""


def check(file_path: str, proposed_content: str, config) -> AstDiffResult:
    lang = config.detect_language(file_path)
    if lang == "unknown":
        return AstDiffResult(
            is_pure_refactor=False,
            reason="Unknown language — cannot classify change",
        )

    try:
        from tree_sitter_languages import get_parser  # type: ignore
    except ImportError:
        # Cannot determine refactor vs. new behavior — keep state machine's BLOCK decision
        return AstDiffResult(
            is_pure_refactor=False,
            reason="tree-sitter-languages not installed; AST check unavailable (run: pip install tree-sitter tree-sitter-languages)",
        )

    ts_lang = _ts_lang(lang)
    try:
        parser = get_parser(ts_lang)
    except Exception as e:
        return AstDiffResult(is_pure_refactor=True, reason=f"Parser unavailable for {ts_lang}: {e}")

    try:
        with open(file_path, "rb") as f:
            current_bytes = f.read()
    except FileNotFoundError:
        current_bytes = b""

    proposed_bytes = proposed_content.encode("utf-8", errors="replace")

    before = _extract_symbols(parser, current_bytes, lang)
    after = _extract_symbols(parser, proposed_bytes, lang)

    new_symbols = after - before
    removed_symbols = before - after
    is_pure_refactor = len(new_symbols) == 0

    return AstDiffResult(
        is_pure_refactor=is_pure_refactor,
        new_symbols=new_symbols,
        removed_symbols=removed_symbols,
        reason=(
            f"New symbols added: {sorted(new_symbols)}" if new_symbols
            else "Structural refactor only — no new symbols"
        ),
    )


def reconstruct_proposed(tool_name: str, tool_input: dict) -> Optional[str]:
    """Reconstruct the full file content that will exist after the edit."""
    file_path = tool_input.get("file_path", "")

    if tool_name == "Write":
        return tool_input.get("content", "")

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            current = f.read()
    except FileNotFoundError:
        current = ""

    if tool_name == "Edit":
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        return current.replace(old, new, 1) if old else current

    if tool_name == "MultiEdit":
        result = current
        for edit in tool_input.get("edits", []):
            old = edit.get("old_string", "")
            new_s = edit.get("new_string", "")
            if old:
                result = result.replace(old, new_s, 1)
        return result

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ts_lang(lang: str) -> str:
    return {"typescript": "typescript", "javascript": "javascript",
            "python": "python", "go": "go"}.get(lang, lang)


def _extract_symbols(parser, content_bytes: bytes, lang: str) -> Set[str]:
    if not content_bytes:
        return set()
    try:
        tree = parser.parse(content_bytes)
    except Exception:
        return set()
    symbols: Set[str] = set()
    _collect(tree.root_node, lang, symbols, depth=0, parent_name=None)
    return symbols


# Node types that introduce a named behavioral symbol per language
_SYMBOL_TYPES = {
    "typescript": {
        "function_declaration", "class_declaration",
        "method_definition", "abstract_method_signature",
    },
    "javascript": {
        "function_declaration", "class_declaration", "method_definition",
    },
    "python": {
        "function_definition", "async_function_definition",
        "class_definition", "decorated_definition",
    },
    "go": {
        "function_declaration", "method_declaration", "type_declaration",
    },
}

# Field names or child types used to find the symbol name
_NAME_CHILD_TYPES = {
    "identifier", "property_identifier", "field_identifier",
    "type_identifier", "name",
}


def _collect(node, lang: str, symbols: Set[str], depth: int, parent_name: Optional[str]):
    if depth > 3:
        return

    target_types = _SYMBOL_TYPES.get(lang, set())
    name = None

    if node.type in target_types:
        name = _get_name(node, lang)
        if name:
            qualifier = f"{parent_name}." if parent_name else ""
            symbols.add(f"{node.type}:{qualifier}{name}")

    for child in node.children:
        _collect(child, lang, symbols, depth + 1, parent_name=name or parent_name)


def _get_name(node, lang: str) -> Optional[str]:
    # Try field-based access first (tree-sitter named fields)
    for field_name in ("name", "field_name"):
        try:
            named = node.child_by_field_name(field_name)
            if named and named.text:
                text = named.text
                return text.decode("utf-8") if isinstance(text, bytes) else str(text)
        except Exception:
            pass

    # Fallback: scan children for identifier-like nodes
    for child in node.children:
        if child.type in _NAME_CHILD_TYPES and child.text:
            text = child.text
            return text.decode("utf-8") if isinstance(text, bytes) else str(text)

    # Python decorated_definition: recurse into the inner def/class
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("function_definition", "async_function_definition", "class_definition"):
                return _get_name(child, lang)

    return None
