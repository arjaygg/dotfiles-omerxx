#!/usr/bin/env python3
"""Build a validated configuration proposal without writing runtime files."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

try:
    from scripts.public_hygiene_check import scan_text
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.public_hygiene_check import scan_text


class TemplateValidationError(ValueError):
    """Raised when a base or overlay contains non-portable content."""


@dataclass(frozen=True)
class ProposalComparison:
    changed_paths: list[str]
    proposal_sha256: str
    target_sha256: str


_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a recursively merged copy; overlay values replace base values."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def expand_placeholders(value: Any, variables: dict[str, str]) -> Any:
    """Replace explicit ``${NAME}`` markers without reading process environment."""
    if isinstance(value, dict):
        expanded: dict[str, Any] = {}
        for key, child in value.items():
            expanded_key = expand_placeholders(key, variables)
            if not isinstance(expanded_key, str):
                raise TemplateValidationError(
                    "template mapping keys must be strings"
                )
            if expanded_key in expanded:
                raise TemplateValidationError(
                    "mapping key collision after placeholder expansion"
                )
            expanded[expanded_key] = expand_placeholders(child, variables)
        return expanded
    if isinstance(value, list):
        return [expand_placeholders(child, variables) for child in value]
    if not isinstance(value, str):
        return copy.deepcopy(value)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise TemplateValidationError(f"unresolved template variable: {name}")
        return variables[name]

    return _PLACEHOLDER.sub(replace, value)


_DocumentFormat = Literal['json', 'toml']
_SUPPORTED_FORMATS: dict[str, _DocumentFormat] = {
    '.json': 'json',
    '.toml': 'toml',
}
_TOML_BARE_KEY = re.compile(r'^[A-Za-z0-9_-]+$')
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_PATH_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PathComponent = str | int
_StructuralPath = tuple[_PathComponent, ...]
_STRICT_FINDING_RULES: frozenset[str] = frozenset()
_COMPARE_LOCAL_CONTEXT_RULES = frozenset(
    {
        "absolute-home-path",
        "private-org-name",
        "private-org-url",
    }
)


def _template_format(path: Path) -> _DocumentFormat:
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_FORMATS:
        expected = ', '.join(sorted(_SUPPORTED_FORMATS))
        raise TemplateValidationError(
            f'{path}: unsupported template format {path.suffix!r}; expected {expected}'
        )
    return _SUPPORTED_FORMATS[suffix]


def _parse_document(
    document: str | bytes,
    document_format: _DocumentFormat,
    path: Path,
    kind: str,
) -> dict[str, Any]:
    try:
        if document_format == 'json':
            value = json.loads(document)
        else:
            text = document.decode('utf-8') if isinstance(document, bytes) else document
            value = tomllib.loads(text)
    except (
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        UnicodeDecodeError,
    ) as error:
        raise TemplateValidationError(
            f'{path}: invalid {document_format.upper()} {kind}: {error}'
        ) from error

    expected_root = 'JSON object' if document_format == 'json' else 'TOML table'
    if not isinstance(value, dict):
        raise TemplateValidationError(
            f'{path}: {kind} root must be a {expected_root}'
        )
    return value


def _decode_target_for_scan(
    document: bytes,
    document_format: _DocumentFormat,
    path: Path,
) -> str:
    encoding = json.detect_encoding(document) if document_format == 'json' else 'utf-8'
    try:
        return document.decode(encoding)
    except UnicodeDecodeError as error:
        raise TemplateValidationError(
            f'{path}: invalid {document_format.upper()} target encoding'
        ) from error


def _mapping_key_words(key: str) -> list[str]:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", key)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", separated)
    return re.findall(r"[A-Za-z0-9]+", separated.lower())


def _is_sensitive_mapping_key(key: str) -> bool:
    words = _mapping_key_words(key)
    if not words:
        return False
    if words[-1] in {
        "apikey",
        "credential",
        "credentials",
        "passphrase",
        "password",
        "secret",
        "token",
    }:
        return True
    return tuple(words[-2:]) in {
        ("api", "key"),
        ("api", "keys"),
        ("password", "hash"),
        ("password", "salt"),
        ("private", "key"),
        ("secret", "value"),
        ("token", "value"),
    }


def _is_safe_sensitive_value(
    value: Any,
    *,
    allow_unresolved_placeholders: bool,
) -> bool:
    if value is None:
        return True
    if isinstance(value, (dict, list)):
        return not value
    if not isinstance(value, str):
        return False
    if not value:
        return True
    if re.fullmatch(r"\[REDACTED(?:[^\]]*)?\]", value):
        return True
    if re.fullmatch(r"<[^>]+>", value):
        return True
    if re.fullmatch(r"YOUR_[A-Z0-9_]+", value):
        return True
    if value in {"CHANGE_ME", "REPLACE_ME"}:
        return True
    return allow_unresolved_placeholders and _PLACEHOLDER.fullmatch(value) is not None


def _raise_structured_finding(context: str, rule: str) -> None:
    raise TemplateValidationError(
        f"{context}: non-portable structured finding: {rule}"
    )


def _validate_structured_content(
    value: Any,
    context: str,
    *,
    allow_unresolved_placeholders: bool,
) -> None:
    if isinstance(value, str):
        if any(
            finding.rule == "private-key"
            for finding in scan_text("<structured-value>", value)
        ):
            _raise_structured_finding(context, "private-key")
        return
    if isinstance(value, list):
        for child in value:
            _validate_structured_content(
                child,
                context,
                allow_unresolved_placeholders=allow_unresolved_placeholders,
            )
        return
    if not isinstance(value, dict):
        return

    for key, child in value.items():
        if isinstance(key, str):
            _validate_structured_content(
                key,
                context,
                allow_unresolved_placeholders=allow_unresolved_placeholders,
            )
        _validate_structured_content(
            child,
            context,
            allow_unresolved_placeholders=allow_unresolved_placeholders,
        )
        if isinstance(key, str) and _is_sensitive_mapping_key(key):
            if not _is_safe_sensitive_value(
                child,
                allow_unresolved_placeholders=allow_unresolved_placeholders,
            ):
                _raise_structured_finding(context, "secret-assignment")


def _validate_portability(
    scan_path: str,
    text: str,
    error_prefix: str,
    *,
    allowed_finding_rules: frozenset[str] = _STRICT_FINDING_RULES,
) -> None:
    findings = [
        finding
        for finding in scan_text(scan_path, text)
        if finding.rule not in allowed_finding_rules
    ]
    if findings:
        summary = ', '.join(f'{finding.rule}@{finding.line}' for finding in findings)
        raise TemplateValidationError(f'{error_prefix}: {summary}')


def _load_template(
    path: Path,
    document_format: _DocumentFormat,
    *,
    allowed_finding_rules: frozenset[str] = _STRICT_FINDING_RULES,
) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8')
    _validate_portability(
        path.as_posix(),
        text,
        f'{path}: non-portable template findings',
        allowed_finding_rules=allowed_finding_rules,
    )
    template = _parse_document(text, document_format, path, 'template')
    _validate_structured_content(
        template,
        str(path),
        allow_unresolved_placeholders=True,
    )
    return template


def _toml_string(value: str) -> str:
    rendered = json.dumps(value, ensure_ascii=False)
    return rendered.replace(chr(127), chr(92) + 'u007F')


def _toml_key(key: Any) -> str:
    if not isinstance(key, str):
        raise TemplateValidationError(
            f'unsupported TOML key type: {type(key).__name__}'
        )
    return key if _TOML_BARE_KEY.fullmatch(key) else _toml_string(key)


def _sorted_toml_keys(data: dict[Any, Any]) -> list[str]:
    keys = list(data)
    for key in keys:
        _toml_key(key)
    return sorted(keys)


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return '-nan' if math.copysign(1.0, value) < 0 else 'nan'
        if math.isinf(value):
            return '-inf' if value < 0 else 'inf'
        return repr(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.time):
        return value.isoformat()
    if isinstance(value, list):
        return '[' + ', '.join(_toml_value(item) for item in value) + ']'
    if isinstance(value, dict):
        parts = [
            f'{_toml_key(key)} = {_toml_value(value[key])}'
            for key in _sorted_toml_keys(value)
        ]
        return '{ ' + ', '.join(parts) + ' }' if parts else '{}'
    raise TemplateValidationError(
        f'unsupported TOML value type: {type(value).__name__}'
    )


def _is_array_of_tables(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
    )


def _toml_path(path: tuple[str, ...]) -> str:
    return '.'.join(_toml_key(part) for part in path)


def dump_toml(data: dict[str, Any]) -> str:
    """Return deterministic TOML for values produced by tomllib."""
    if not isinstance(data, dict):
        raise TemplateValidationError('TOML document root must be a table')

    lines: list[str] = []

    def append_header(header: str) -> None:
        if lines:
            lines.append('')
        lines.append(header)

    def dump_section(path: tuple[str, ...], section: dict[str, Any]) -> None:
        keys = _sorted_toml_keys(section)
        for key in keys:
            value = section[key]
            if not isinstance(value, dict) and not _is_array_of_tables(value):
                lines.append(f'{_toml_key(key)} = {_toml_value(value)}')

        for key in keys:
            value = section[key]
            if isinstance(value, dict):
                child_path = (*path, key)
                append_header(f'[{_toml_path(child_path)}]')
                dump_section(child_path, value)

        for key in keys:
            value = section[key]
            if _is_array_of_tables(value):
                child_path = (*path, key)
                for item in value:
                    append_header(f'[[{_toml_path(child_path)}]]')
                    dump_section(child_path, item)

    dump_section((), data)
    return chr(10).join(lines) + chr(10)


def _values_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and math.isnan(left):
        return math.isnan(right) and math.copysign(1.0, left) == math.copysign(
            1.0, right
        )
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _render_proposal(
    base_path: Path,
    overlay_path: Path | None,
    variables: dict[str, str] | None,
    *,
    comparison_mode: bool,
) -> str:
    allowed_finding_rules = (
        _COMPARE_LOCAL_CONTEXT_RULES
        if comparison_mode
        else _STRICT_FINDING_RULES
    )
    document_format = _template_format(base_path)
    if overlay_path is not None:
        overlay_format = _template_format(overlay_path)
        if overlay_format != document_format:
            raise TemplateValidationError(
                f'{overlay_path}: overlay format does not match '
                f'base format {base_path.suffix.lower()}'
            )
    else:
        overlay_format = document_format

    base = _load_template(base_path, document_format)
    overlay = (
        _load_template(
            overlay_path,
            overlay_format,
            allowed_finding_rules=allowed_finding_rules,
        )
        if overlay_path is not None
        else {}
    )
    proposal = expand_placeholders(deep_merge(base, overlay), variables or {})
    _validate_structured_content(
        proposal,
        'proposal',
        allow_unresolved_placeholders=False,
    )

    if document_format == 'toml':
        rendered = dump_toml(proposal)
        try:
            parsed = tomllib.loads(rendered)
        except tomllib.TOMLDecodeError as error:
            raise TemplateValidationError(
                f'proposal: generated invalid TOML: {error}'
            ) from error
        if not _values_equal(parsed, proposal):
            raise TemplateValidationError(
                'proposal: generated TOML changed document semantics'
            )
    else:
        rendered = json.dumps(proposal, indent=2, sort_keys=True) + chr(10)

    _validate_portability(
        '<proposal>',
        rendered,
        'proposal: non-portable findings',
        allowed_finding_rules=allowed_finding_rules,
    )
    return rendered


def build_proposal(
    base_path: Path,
    overlay_path: Path | None = None,
    variables: dict[str, str] | None = None,
) -> str:
    """Return merged JSON or TOML for review without writing files."""
    return _render_proposal(
        base_path,
        overlay_path,
        variables,
        comparison_mode=False,
    )


def _mapping_key_needs_redaction(key: str) -> bool:
    return (
        key.startswith(("/", "~/"))
        or _WINDOWS_DRIVE_PATH.match(key) is not None
        or bool(scan_text("<changed-path-key>", key))
    )


def _flatten(
    value: Any,
    prefix: _StructuralPath = (),
) -> dict[_StructuralPath, Any]:
    if isinstance(value, dict):
        if not value:
            return {prefix: value}
        flattened: dict[_StructuralPath, Any] = {}
        for key, child in value.items():
            flattened.update(_flatten(child, (*prefix, key)))
        return flattened
    if isinstance(value, list):
        if not value:
            return {prefix: value}
        flattened = {}
        for index, child in enumerate(value):
            flattened.update(_flatten(child, (*prefix, index)))
        return flattened
    return {prefix: value}


def _format_changed_paths(paths: list[_StructuralPath]) -> list[str]:
    mapping_keys = {
        component
        for path in paths
        for component in path
        if isinstance(component, str)
    }
    redacted_keys = sorted(
        key for key in mapping_keys if _mapping_key_needs_redaction(key)
    )
    labels = {
        key: f"<redacted-key-{index}>"
        for index, key in enumerate(redacted_keys, start=1)
    }

    def format_path(path: _StructuralPath) -> str:
        rendered = ""
        for component in path:
            if isinstance(component, int):
                rendered += f"[{component}]"
                continue
            if component in labels:
                label = labels[component]
                rendered += f".{label}" if rendered else label
                continue
            if _PATH_IDENTIFIER.fullmatch(component):
                rendered += f".{component}" if rendered else component
                continue
            rendered += f"[{json.dumps(component, ensure_ascii=False)}]"
        return rendered

    return sorted(format_path(path) for path in paths)


def compare_proposal(
    base_path: Path,
    overlay_path: Path | None,
    target_path: Path,
    variables: dict[str, str] | None = None,
) -> ProposalComparison:
    """Compare a proposal with a target without printing target contents."""
    document_format = _template_format(base_path)
    proposal_text = _render_proposal(
        base_path,
        overlay_path,
        variables,
        comparison_mode=True,
    )
    target_bytes = target_path.read_bytes()
    target_text = _decode_target_for_scan(
        target_bytes,
        document_format,
        target_path,
    )
    _validate_portability(
        target_path.as_posix(),
        target_text,
        f'{target_path}: non-portable target findings',
        allowed_finding_rules=_COMPARE_LOCAL_CONTEXT_RULES,
    )
    target = _parse_document(
        target_bytes,
        document_format,
        target_path,
        'target',
    )
    _validate_structured_content(
        target,
        str(target_path),
        allow_unresolved_placeholders=False,
    )
    proposal = _parse_document(
        proposal_text,
        document_format,
        Path('<proposal>'),
        'proposal',
    )
    proposal_values = _flatten(proposal)
    target_values = _flatten(target)
    changed_structural_paths = [
        path
        for path in proposal_values.keys() | target_values.keys()
        if path not in proposal_values
        or path not in target_values
        or not _values_equal(proposal_values[path], target_values[path])
    ]
    changed_paths = _format_changed_paths(changed_structural_paths)
    return ProposalComparison(
        changed_paths=changed_paths,
        proposal_sha256=hashlib.sha256(proposal_text.encode('utf-8')).hexdigest(),
        target_sha256=hashlib.sha256(target_bytes).hexdigest(),
    )


def _parse_variables(values: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for value in values:
        name, separator, replacement = value.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise TemplateValidationError(f"invalid --set value: {value!r}")
        variables[name] = replacement
    return variables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--compare-against", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args(argv)
    try:
        variables = _parse_variables(args.set)
        if args.compare_against:
            print(
                json.dumps(
                    asdict(
                        compare_proposal(
                            args.base, args.overlay, args.compare_against, variables
                        )
                    )
                )
            )
        else:
            sys.stdout.write(build_proposal(args.base, args.overlay, variables))
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        TemplateValidationError,
    ) as error:
        print(f"config proposal rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
