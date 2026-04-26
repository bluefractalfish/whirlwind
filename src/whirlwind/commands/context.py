"""whirlwind.commands.context

    shared configuration context 

"""

from dataclasses import dataclass 
from pathlib import Path 
from typing import Any 

from whirlwind.domain.config import Config 
from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.adapters.filesystem.pathfinder import find_home_

FALLBACKS: dict[str, str] = {
        "in_dir": "./mnt",
        "dest_dir": "./artifacts/",
        "run_id": "dev"
        }

@dataclass(frozen=True)
class CommandContext: 
    """ 
        shared configuration context 
            
        properties 
        ----------
        globalconfig -> dict
        io -> dict
        in_dir -> Path
        dest_dir -> Path 
        run_id -> str 
        run_tree -> RunTree 

        methods 
        ----------- 
        section(*keys: str) -> dict[str, Any]
        value(self, *keys: str, default: Any=None) -> Any 


    """

    config: Config 
    
    @property 
    def projectroot(self) -> Path:
        return find_home_()
    
    @property 
    def globalconfig(self) -> dict[str, Any]:
        value = self.config.merged.get("global",{})
        return value if isinstance(value, dict) else {}


    @property 
    def io(self) -> dict[str, Any]:
        value = self.globalconfig.get("io",{})
        return value if isinstance(value, dict) else {}

    @property 
    def in_dir(self) -> Path: 
        return Path(self.io.get("in_dir",FALLBACKS["in_dir"])).expanduser().resolve()
    

    @property
    def dest_dir(self) -> Path:
        return Path(self.io.get("dest_dir", FALLBACKS["dest_dir"])).expanduser().resolve()

    @property
    def run_id(self) -> str:
        return str(self.globalconfig.get("run_id", FALLBACKS["run_id"]))

    @property
    def run_tree(self) -> RunTree:
        return RunTree.plant(self.dest_dir / self.run_id)

    def resolve_path(self, value: str | Path) -> Path:
        """
        Resolve config/user paths relative to the project root.

        This prevents ./mnt from resolving relative to src/whirlwind
        when the shell is launched from inside the package directory.
        """
        path = Path(value).expanduser()

        if path.is_absolute():
            return path.resolve()

        return (self.projectroot / path).resolve()

    def section(self, *keys: str) -> dict[str, Any]:
        obj: Any = self.config.merged
        for key in keys:
            if not isinstance(obj, dict):
                return {}
            obj = obj.get(key, {})
        return obj if isinstance(obj, dict) else {}

    def value(self, *keys: str, default: Any = None) -> Any:
        obj: Any = self.config.merged
        for key in keys:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(key, default)
        return obj
