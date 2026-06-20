from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Iterator

from whirlwind.domain.plannedwindow import PlannedWindow


FIELDNAMES = [
    "row_i",
    "col_i",
    "x",
    "y",
    "w",
    "h",
]


class WindowPlanCSV:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def write(self, rows: Iterable[PlannedWindow], *, force: bool = False) -> int:
        if self.path.exists() and not force:
            return 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

            for row in rows:
                writer.writerow(row.record())
                n += 1

        return n

    def count(self) -> int:
            if not self.path.is_file() or not self.path.exists():
                print("no window plan has been made")
                raise FileNotFoundError

            with self.path.open("r", newline="", encoding="utf-8") as f:
                return max(0, sum(1 for _ in f) - 1)

    def read(self) -> Iterator[PlannedWindow]:
        if not self.path.is_file() or not self.path.exists():
            print("no window plan has been made")
            raise FileNotFoundError

        with self.path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for record in reader:
                yield PlannedWindow.read(record)
