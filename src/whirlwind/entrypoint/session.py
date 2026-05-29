from dataclasses import dataclass 
from typing import Literal 


ScopeKind = Literal["root","metamosaic","mosaic"]

@dataclass 
class ShellScope:
    kind: ScopeKind = "root"
    metamosaic_id: str | None = None 
    mosaic_id: str | None = None 

    def clear(self) -> None:
        self.kind = "root"
        self.metamosaic_id = None 
        self.mosaic_id = None 


    def cd_metamosaic(self, metamosaic_id: str) -> None: 
        self.kind = "metamosaic"
        self.metamosaic_id = metamosaic_id 
        self.mosaic_id = None 

    def cd_mosaic(self, mosaic_id: str, metamosaic_id: str | None =None) -> None: 
        self.kind = "mosaic"
        self.mosaic_id = mosaic_id 
        self.metamosaic_id = metamosaic_id 

    def working_dir(self) -> str: 
        if self.kind == "root":
            return "/"
        if self.kind == "metamosaic":
            return f"{self.metamosaic_id}"
        return f"{self.mosaic_id}"


@dataclass 
class ShellSettings: 
    dry_run: bool = False 
    quiet: bool = False 


@dataclass 
class ShellSession: 
    scope: ShellScope 
    settings: ShellSettings 

    @classmethod 
    def new(cls) -> "ShellSession":
        return cls(
                scope=ShellScope(),
                settings=ShellSettings(),
                ) 


