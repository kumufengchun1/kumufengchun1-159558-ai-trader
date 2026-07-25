from pathlib import Path

import yaml

from ats.domain import Asset


def load_assets(path: Path) -> list[Asset]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Asset(**item) for item in payload["assets"]]
