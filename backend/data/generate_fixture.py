from pathlib import Path

from app.fixture import build_snapshot

destination = Path(__file__).with_name("stations.json")
destination.write_text(build_snapshot().model_dump_json(indent=2) + "\n", encoding="utf-8")
print(f"Wrote {destination}")
