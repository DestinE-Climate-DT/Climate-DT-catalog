"""Per-dataset JSON state kept in the work directory (upstream signatures, last runs)."""

import datetime
import json
from pathlib import Path


class State:
    """Dict-like JSON store, one file per dataset."""

    def __init__(self, workdir, dataset):
        self.path = Path(workdir) / "state" / f"{dataset}.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, product, key, default=None):
        return self.data.get(product, {}).get(key, default)

    def set(self, product, **values):
        entry = self.data.setdefault(product, {})
        entry.update(values)
        entry["updated"] = datetime.datetime.now().isoformat(timespec="seconds")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True))
        tmp.replace(self.path)
