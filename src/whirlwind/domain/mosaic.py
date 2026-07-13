from dataclasses import dataclass 
from pathlib import Path 



@dataclass(frozen=True)
class MosaicRecord: 
    mosaic_id: str 
    alias: str 
    path: Path 
    source_uri: str 
    date: str 
    variant_id: str 
    variant_type: str = ""
    spectral_id: str = ""
    branch_id: str | None=None 
    metamosaic_id: str | None=None 
    metamosaic_alias: str | None=None
    id_scheme: str = ""
    id_version: str = ""

    @classmethod 
    def from_row(cls, row: dict[str, str]) -> "MosaicRecord":
    
        # for legacy, added file_id, id 
        mosaic_id = row.get("mosaic_id") or row.get("file_id") or row.get("id")
        alias = row.get("alias")

        if not mosaic_id:
            raise ValueError(f"manifest row missing mosaic id: {row}")
        if not alias: 
            raise ValueError(f"manifest row missing alias: {row}")
        path_raw = row.get("path") or ""
        if not path_raw:
            raise ValueError(f"manifest row missing path: {row}")

        return cls(
            mosaic_id=mosaic_id,
            alias=alias,
            path=Path(path_raw),
            source_uri=row.get("source_uri") or row.get("uri") or "",
            date=row.get("date") or "",
            variant_id=row.get("variant_id") or "",
            variant_type=row.get("variant_type") or "",
            spectral_id=row.get("spectral_id") or "",
            branch_id=row.get("branch_id") or None,
            metamosaic_id=row.get("metamosaic_id") or None,
            metamosaic_alias=row.get("metamosaic_alias") or None,
            id_scheme=row.get("id_scheme") or "",
            id_version=row.get("id_version") or "",
        )


