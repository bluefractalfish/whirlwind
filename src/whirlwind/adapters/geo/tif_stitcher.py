
from pathlib import Path 
from osgeo import gdal 

class TifStitcher: 
    def __init__(self, branch, request ) -> None: 
        self.branch = branch 
        self.request = request 
       
    def stitch(self) -> tuple[int,str]: 
        tiles_dir = self.branch.tiles_dir 
        out_dir = tiles_dir / self.request.out_dir_name 
        out_dir.mkdir(parents=True, exist_ok=True)

        for group_dir in sorted(p for p in tiles_dir.iterdir() if p.is_dir()):

            if group_dir.name == self.request.out_dir_name:
                continue

            tif_paths = sorted(
                p for p in group_dir.glob(self.request.pattern)
                if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}
            )

            if not tif_paths:
                return 1, f"{tif_paths} does not exist"

            vrt_path = out_dir / f"{self.branch.mosaic_id}-{group_dir.name}.vrt"
            tif_path = out_dir / f"{self.branch.mosaic_id}-{group_dir.name}.tif"

            if tif_path.exists() and not self.request.overwrite:
                continue

            try:
                self._build_vrt(vrt_path, tif_paths, overwrite=self.request.overwrite)

                self._translate_vrt(
                    vrt_path=vrt_path,
                    tif_path=tif_path,
                    overwrite=self.request.overwrite,
                    bigtiff=self.request.bigtiff,
                    tiled=self.request.tiled,
                    compress=self.request.compress,
                )


            except Exception as e:
                return 1, str(e)

        return 0, "success"


    def _build_vrt(
        self,
        vrt_path: Path,
        tif_paths: list[Path],
        overwrite: bool,
    ) -> None:

        if vrt_path.exists() and overwrite:
            vrt_path.unlink()

        if vrt_path.exists() and not overwrite:
            return

        ds = gdal.BuildVRT(
            str(vrt_path),
            [str(p) for p in tif_paths],
        )

        if ds is None:
            raise RuntimeError(f"gdal.BuildVRT failed: {vrt_path}")

        ds = None

    def _translate_vrt(
        self,
        vrt_path: Path,
        tif_path: Path,
        overwrite: bool,
        bigtiff: str,
        tiled: bool,
        compress: str,
    ) -> None:
        if tif_path.exists() and overwrite:
            tif_path.unlink()

        if tif_path.exists() and not overwrite:
            return

        creation_options = [
            f"BIGTIFF={bigtiff}",
            f"COMPRESS={compress}",
        ]

        if tiled:
            creation_options.append("TILED=YES")

        ds = gdal.Translate(
            str(tif_path),
            str(vrt_path),
            format="GTiff",
            creationOptions=creation_options,
        )

        if ds is None:
            raise RuntimeError(f"gdal.Translate failed: {tif_path}")

        ds = None


