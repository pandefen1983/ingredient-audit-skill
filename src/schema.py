from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


LIST_FIELDS = ("exclude_terms", "allow_terms", "fail_patterns", "warn_patterns")


@dataclass(frozen=True)
class RuleSet:
    preset: str
    mode: str | None
    options: tuple[str, ...]
    description: str
    exclude_terms: tuple[str, ...] = field(default_factory=tuple)
    allow_terms: tuple[str, ...] = field(default_factory=tuple)
    fail_patterns: tuple[dict[str, str], ...] = field(default_factory=tuple)
    warn_patterns: tuple[dict[str, str], ...] = field(default_factory=tuple)
    max_ingredient_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "mode": self.mode,
            "options": list(self.options),
            "description": self.description,
            "exclude_terms": list(self.exclude_terms),
            "allow_terms": list(self.allow_terms),
            "fail_patterns": list(self.fail_patterns),
            "warn_patterns": list(self.warn_patterns),
            "max_ingredient_count": self.max_ingredient_count,
        }


def _dedupe(items: Iterable[Any]) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for item in items:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            output.append(item)
    return output


def _merge_rules(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in LIST_FIELDS:
        merged[key] = _dedupe([*left.get(key, []), *right.get(key, [])])
    if "max_ingredient_count" in right:
        merged["max_ingredient_count"] = right["max_ingredient_count"]
    return merged


def _resolve_mode(modes: dict[str, Any], name: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
    if name not in modes:
        raise ValueError(f"Unknown mode: {name}")
    if name in stack:
        raise ValueError(f"Circular mode inheritance: {' -> '.join((*stack, name))}")
    current = modes[name]
    parent = current.get("inherits")
    inherited = _resolve_mode(modes, parent, (*stack, name)) if parent else {}
    return _merge_rules(inherited, current)


def load_preset(
    name: str,
    mode: str | None = None,
    options: Iterable[str] | None = None,
    custom_exclusions: Iterable[str] | None = None,
    presets_dir: str | Path | None = None,
) -> RuleSet:
    root = Path(presets_dir) if presets_dir else Path(__file__).resolve().parents[1] / "presets"
    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    path = root / filename
    if not path.is_file():
        raise FileNotFoundError(f"Preset not found: {path}")

    # Presets use the JSON-compatible subset of YAML to keep the project dependency-free.
    data = json.loads(path.read_text(encoding="utf-8"))
    selected_mode = mode or data.get("default_mode")
    rules = dict(data.get("base", {}))
    if selected_mode:
        rules = _merge_rules(rules, _resolve_mode(data.get("modes", {}), selected_mode))
    selected_options = list(options or [])
    available_options = data.get("optional_rules", {})
    for option in selected_options:
        if option not in available_options:
            raise ValueError(f"Unknown option: {option}")
        rules = _merge_rules(rules, available_options[option])
    if custom_exclusions:
        rules = _merge_rules(rules, {"exclude_terms": list(custom_exclusions)})

    return RuleSet(
        preset=data["name"],
        mode=selected_mode,
        options=tuple(selected_options),
        description=data.get("description", ""),
        exclude_terms=tuple(rules.get("exclude_terms", [])),
        allow_terms=tuple(rules.get("allow_terms", [])),
        fail_patterns=tuple(rules.get("fail_patterns", [])),
        warn_patterns=tuple(rules.get("warn_patterns", [])),
        max_ingredient_count=rules.get("max_ingredient_count"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a Product Finder preset.")
    parser.add_argument("preset")
    parser.add_argument("--mode")
    parser.add_argument("--option", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            load_preset(args.preset, args.mode, args.option, args.exclude).as_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
