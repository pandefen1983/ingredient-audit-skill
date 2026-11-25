"""Category traversal plans.

Keyword search only reaches listings whose title contains the keyword. Large
marketplaces cap a query at roughly 100 pages and rank by sales, so long-tail
SKUs never surface. Walking the category itself, split by price band, recovers
listings that a keyword search cannot see.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config"
DEFAULT_PLATFORMS = CONFIG_ROOT / "platforms.yaml"


@dataclass(frozen=True)
class CategoryTask:
    """One (platform, category, price band) traversal."""

    platform: str
    category: str
    price_band: tuple[float | None, float | None]
    pages: int
    tier: int = 2

    @property
    def requests(self) -> int:
        return self.pages

    def as_dict(self) -> dict[str, Any]:
        low, high = self.price_band
        return {
            "platform": self.platform,
            "category": self.category,
            "price_min": low,
            "price_max": high,
            "pages": self.pages,
            "tier": self.tier,
            "requests": self.requests,
        }


def load_platforms(path: Path | str | None = None) -> dict[str, Any]:
    """Load per-platform traversal config (JSON-compatible YAML)."""
    target = Path(path) if path else DEFAULT_PLATFORMS
    return json.loads(Path(target).read_text(encoding="utf-8"))


def build_category_tasks(
    platforms: Iterable[str],
    config: dict[str, Any],
    category: str | None = None,
    max_pages: int | None = None,
) -> list[CategoryTask]:
    """One task per platform x price band, for the requested category."""
    tasks: list[CategoryTask] = []
    for platform in platforms:
        entry = config.get(platform)
        if not entry:
            continue
        paths = entry.get("category", {})
        if category is None:
            names = list(paths.keys())
        else:
            names = [category] if category in paths else []
        for name in names:
            pages = int(entry.get("max_pages_per_band", 2))
            if max_pages is not None:
                pages = min(pages, max_pages)
            for band in entry.get("price_bands", []):
                low, high = (band + [None, None])[:2] if isinstance(band, list) else (None, None)
                tasks.append(
                    CategoryTask(
                        platform=platform,
                        category=paths[name],
                        price_band=(low, high),
                        pages=pages,
                    )
                )
    return tasks


def request_interval(platform: str, config: dict[str, Any]) -> float:
    """Minimum seconds between two requests on this platform."""
    entry = config.get(platform) or {}
    return float(entry.get("request_interval_seconds", 1.0))
