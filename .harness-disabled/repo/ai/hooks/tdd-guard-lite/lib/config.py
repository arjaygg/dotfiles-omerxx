"""Per-project configuration loader with sensible defaults."""
import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Config:
    language: str = "auto"
    test_results_path: str = ".claude/tdd-guard/data/test.json"
    modifications_path: str = ".claude/tdd-guard/data/modifications.json"
    coverage_path: Optional[str] = None
    source_patterns: List[str] = field(default_factory=lambda: [
        "src/**/*.ts", "src/**/*.tsx", "src/**/*.js", "src/**/*.jsx", "src/**/*.mjs",
        "src/**/*.py", "**/*.go",
    ])
    test_patterns: List[str] = field(default_factory=lambda: [
        "**/*.test.ts", "**/*.spec.ts", "**/*.test.tsx", "**/*.spec.tsx",
        "**/*.test.js", "**/*.spec.js", "**/*.test.mjs",
        "**/*_test.py", "**/test_*.py",
        "**/*_test.go",
    ])
    ast_diff_enabled: bool = True
    recent_modification_window: int = 10

    def is_test_file(self, path: str) -> bool:
        return _matches_any(path, self.test_patterns)

    def is_source_file(self, path: str) -> bool:
        return _matches_any(path, self.source_patterns)

    def detect_language(self, path: str) -> str:
        if self.language != "auto":
            return self.language
        ext = Path(path).suffix.lower()
        return {
            ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
            ".py": "python",
            ".go": "go",
        }.get(ext, "unknown")


def load_config() -> Config:
    config_path = ".claude/tdd-guard-lite.json"
    overrides = {}
    try:
        with open(config_path) as f:
            overrides = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    c = Config()
    for key, value in overrides.items():
        attr = _to_snake(key)
        if hasattr(c, attr):
            setattr(c, attr, value)
    return c


def _matches_any(path: str, patterns: List[str]) -> bool:
    norm = path.lstrip("/")
    name = Path(path).name
    for pattern in patterns:
        if fnmatch.fnmatch(norm, pattern):
            return True
        # Match bare filename against the last path component of the pattern
        # so "**/test_*.py" matches "test_foo.py" and "src/**/*.ts" matches "foo.ts"
        name_pattern = pattern.split("/")[-1]
        if fnmatch.fnmatch(name, name_pattern):
            return True
    return False


def _to_snake(camel: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", camel)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
