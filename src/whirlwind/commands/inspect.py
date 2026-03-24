
from whirlwind.imps import *
from .base import Command
from ..utils import pathfinder as pf
from ..utils import ids
from ..utils import readwrite as rwr
from ..utils import logger
from ..ui.tui import TUI 

class InspectCommand(Command):
    name = "inspect"
    
    def __init__(self):
        self.ui = TUI()

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:
        


        cfg = self._config(config)
       
        if len(tokens) == 0:
            self.ui.error("more tokens are required for inspection")
        if tokens:
            cfg["root"] = tokens[0]
        else: 
            self.ui.error("root path needed")
        root = Path(cfg["root"])

        if not root.exists() or not root.is_dir():
            self.ui.error(f"not a valid path: {root}")
            return 2

        out_name = f"{ids.gen_fingerprint(root)}.csv"
        metadata_dir = pf._find_home_() / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        csv_path = metadata_dir / out_name

        if not csv_path.exists():
            rwr.write_metadata(str(root), out_name)

        stats = inspect_metadata(csv_path, top_n=cfg["top_n"])
        self.ui.print(f"dirs={stats.num_dirs} files={stats.num_files} bytes={stats.total_bytes}")
        return 0

    def _config(self, config: dict[str, Any]) -> dict[str, Any]:
        inspect_cfg = config.get("inspect", {})
        self.ui.print("sourcing configuration for _inspect_")
        if not isinstance(inspect_cfg, dict):
            inspect_cfg = {}

        cfg = {
            "root": None,
            "top_n": 500,
        }
        cfg.update(inspect_cfg)


        return cfg
    def help(self) -> dict[str,str]:
        tr = { 
            "inspect": "the inspect command is for scanning directories and generating csv manifests of the contents. it handles the generation of uris, uids, fingerprints. when referenced with the <ingest> command these csvs are used to produce tesselations of the mosaics located at the given uris"
              }
        return tr

@dataclass
class ScanStats:
    num_dirs: int = 0
    num_files: int = 0
    total_bytes: int = 0
    largest: list[tuple[int, str, str, str]] = field(default_factory=list)


def inspect_metadata(csv_path: Path, top_n: int = 500) -> ScanStats:
    stats = ScanStats()
    parent_dirs: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = (row.get("uri") or "").strip()
            if not uri:
                continue

            size_text = (row.get("byte_size") or "").strip()
            try:
                size = int(size_text) if size_text else 0
            except ValueError:
                size = 0

            dtype = (row.get("dtype") or "").strip()
            band_count = (row.get("band_count") or "").strip()

            stats.num_files += 1
            stats.total_bytes += size
            parent_dirs.add(str(Path(uri).parent))

            if top_n > 0:
                item = (size, uri, dtype, band_count)
                if len(stats.largest) < top_n:
                    heapq.heappush(stats.largest, item)
                elif size > stats.largest[0][0]:
                    heapq.heapreplace(stats.largest, item)

    stats.num_dirs = len(parent_dirs)
    return stats
