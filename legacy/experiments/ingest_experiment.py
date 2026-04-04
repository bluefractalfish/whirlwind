from whirlwind.imps import * 
from itertools import product

from ..commands.tessera.tile import Tiler 
from ..utils import readwrite as rwr 

@dataclass 
class IngestTilesExperiment: 
    files_in: str
    log: Any
    grid: dict[str, list[Any]]
    out_root: Path
    rows: list[dict[str, Any]] = field(default_factory=list)

    def iter_configs(self) -> Iterator[dict[str, Any]]:
        keys = list(self.grid.keys())
        values = [self.grid[k] for k in keys]
        print(math.prod(len(v) for v in values))
        for combo in product(*values):
            cfg = dict(zip(keys, combo))
            if self.valid_config(cfg):
                yield cfg

    def valid_config(self, cfg: dict[str, Any]) -> bool:
        tile_size = cfg.get("tile_size")
        stride = cfg.get("stride")
        scale = cfg.get("scale")
        p_low = cfg.get("p_low")
        p_high = cfg.get("p_high")

        if tile_size is None or tile_size <= 0: 
            return False 
        if stride is None or stride <=0 or stride > tile_size: 
            return False 
        if scale == "percentile": 
            if p_low is None or p_high is None:
                return False 
            if not (0.0 <= p_low < p_high <= 100.00):
                return False 
        return True 
    def run_id(self, i: int) -> str:
        return f"exp-{i:03d}"

    def run(self) -> int:
        self.out_root.mkdir(parents=True,exist_ok=True)
        sink = None 
        try:
            for i, cfg in enumerate(self.iter_configs(),start=1):

                run_id = self.run_id(i)
                run_out = self.out_root / run_id 
                run_out.mkdir(parents=True,exist_ok=True)

                run_cfg = dict(cfg)
                run_cfg["input"] = self.files_in
                run_cfg = {
                "ingest": {
                    "tiles": {
                        "out": str(run_out),
                        "tile_size": cfg["tile_size"],
                        "stride": cfg["stride"],
                        "drop_partial": cfg["drop_partial"],
                        "shard_size": cfg["shard_size"],
                        "manifest": cfg["manifest"],
                        "dtype": cfg["dtype"],
                        "scale": cfg["scale"],
                        "p_low": cfg["p_low"],
                        "p_high": cfg["p_high"],
                        "per_band": cfg["per_band"],
                        "stats": cfg["stats"],
                        "num_samples": cfg["num_samples"],
                        }
                    }
                }

                tiler = Tiler(self.files_in,run_cfg, self.log)
                metrics = tiler.run_experiment()
                
                row = { 
                    "run_id": run_id,
                       **cfg,
                       **metrics,
                    }
                
                self.add_derived_metrics(row)
                if sink is None:
                    results_path = self.out_root / "results.csv"
                    sink = rwr.ResultsCSVSink(results_path,list(row.keys()))
                sink._write(row)
            return 1
        finally: 
            if sink is not None:
                sink._close()



    def add_derived_metrics(self, row: dict[str,Any]) -> None:
        total_written = row.get("total_written", 0) or 0
        total_seconds = row.get("total_seconds", 0.0) or 0.0
        out_bytes = row.get("out_bytes", 0) or 0
        shard_bytes = row.get("shard_bytes", 0) or 0
        raw_bytes = row.get("raw_bytes", 0) or 0

        row["tiles_per_second"] = (
            total_written / total_seconds
            if total_written > 0 and total_seconds > 0
            else 0.0
        )

        row["bytes_per_tile"] = (
            out_bytes / total_written
            if total_written > 0
            else 0.0
        )
