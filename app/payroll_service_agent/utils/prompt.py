import yaml

from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Union

def load_prompt(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "prompts" / f"{name}.yml"
    with open(path, "r", encoding='utf-8') as f:
        return yaml.safe_load(f)