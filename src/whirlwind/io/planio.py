
from typing import Iterator, Any, Iterable 
from pathlib import Path 
import json 
import csv 


from dataclasses import dataclass, asdict, fields
from whirlwind.specs import TSpec 
from whirlwind.filetrees import RunTree, MosaicBranch


@dataclass(frozen=True) 
class PlanRow:
    row_i: int 
    col_i: int 
    x: int 
    y: int 
    w: int 
    h: int

    def record(self) -> dict[str,int]:
        return asdict(self)


    @classmethod 
    def read(cls, data: dict[str, Any]) -> "PlanRow":
        return cls( 
                   row_i = int(data["row_i"]),
                   col_i = int(data["col_i"]),
                   x  = int(data["x"]),
                   y  = int(data["y"]),
                   w  = int(data["w"]),
                   h  = int(data["h"])
                )

class TilePlanIO: 
    branch: MosaicBranch 
    spec: TSpec 
    
    def __init__(self, branch: MosaicBranch, spec: TSpec ) -> None:
        self.branch = branch 
        branch.ensure()
        self.spec = spec
    
    @property 
    def csv_exists(self) -> bool:
        path = self.csv_path 
        return path.exists() and path.stat().st_size > 0

    @property 
    def csv_path(self) -> Path:
        tile_size = self.spec.tile_size 
        stride = self.spec.stride 
        name = f"tile_plan_{tile_size}_{stride}.csv"
        return self.branch.manifest_dir/name

    @property 
    def json_path(self) -> Path: 
        tile_size = self.spec.tile_size 
        stride = self.spec.stride 
        name = f"tile_plan_{tile_size}_{stride}.json"
        return self.branch.manifest_dir/name 

    @staticmethod 
    def fieldnames() -> list[str]:
        return [f.name for f in fields(PlanRow)]

    def append_csv(self, row: PlanRow) -> None:
        path = self.csv_path
        exists = path.exists() and path.stat().st_size > 0 

        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames = self.fieldnames())
            if not exists:
                writer.writeheader()
            writer.writerow(row.record()) 

    def write_csv(self, rows: Iterable[PlanRow]) -> None:
        path = self.csv_path
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames())
            writer.writeheader()
            for row in rows:
                writer.writerow(row.record())

    def read_csv(self) -> Iterator[PlanRow]:
        path = self.csv_path
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield PlanRow.read(row)

    def write_json(self, rows: Iterable[PlanRow]) -> None:
        path = self.json_path
        payload = [row.record() for row in rows]
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def read_json(self) -> Iterator[PlanRow]:
        path = self.json_path
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("tile_plan.json must contain a list of rows")

        for item in data:
            if not isinstance(item, dict):
                raise ValueError("each plan row must be a json object")
            yield PlanRow.read(item)
