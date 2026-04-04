
"""whirlwind.geo.downsample 
    PURPOSE:
        - holds logic for downsampling mosaics 
    BEHAVIOR:
        - using DSParams to hold user configuration, downsample using a subprocess 
        `gdal_translate` command or uses the gdal api to return downsampled geotiff with 
        preserved geodata 

"""
from osgeo import ogr, osr
import subprocess 
from osgeo import gdal 
from pathlib import Path 
from whirlwind.ui import face
from whirlwind.tools.ids import gen_uuid_from_str
from whirlwind.tools.timer import timed 

from dataclasses import dataclass 
from typing import Optional, Tuple, Union, List, Any, Dict

@timed("downsampling")
def downsample_mosaic(source_path: Path,  params: DSParams, subproc: bool=True) -> Path:
    return build_gdal_subprocess(source_path, params) 

def build_gdal_subprocess(source_path: Path,  params: DSParams) -> Path:

    cmd = ["gdal_translate","-q","-of", "GTiff"]
    if params.dtype:
        cmd += ["-ot",params.dtype]
    if params.target_resolution:
        xres, yres = params.target_resolution 
        cmd += ["-tr",str(xres),str(yres)]
    elif params.scale_factor: 
        pct = int(params.scale_factor * 100)
        cmd += ["-outsize", f"{pct}%",f"{pct}%"]
    elif params.target_width or params.target_height:
        width = str(params.target_width or 0)
        height = str(params.target_height or 0)
        cmd += ["-outsize", width, height]

    if params.resampling:
        cmd += ["-r", params.resampling] 
    
    if params.nodata is not None:
        cmd += ["-a_nodata", str(params.nodata)]

    co_opts = []

    if params.compression:
        co_opts.append(f"COMPRESS={params.compression}")
    if params.tiled:
        co_opts.append("TILED=YES")
    for co in co_opts:
        cmd += ["-co",co]
    cmd += ["--config","GDAL_TRANSLATE_COPY_SRC_MDD", "YES"]
    out_path = downsample_dir(str(source_path), params.out_dir)
    cmd += [source_path, out_path]
    face.process(str(source_path),"gdal_translate",f"{out_path.name}")
    subprocess.run(cmd, check=True)

    ## change names of PATHSS
    return Path(params.out_dir) / f"{gen_uuid_from_str(str(source_path))}"



@dataclass 
class DSParams:
    """downsample params for gdal_translate """
    uris: list[str]
    out_dir: Path 
    target_resolution: Optional[Tuple[float, float]] = None 
    scale_factor: Optional[float] = None 
    target_width: Optional[int] = None 
    target_height: Optional[int] = None 
    resampling: str = 'nearest' # nearest, bilinear, cubic, average
    dtype: Optional[str] = None # byte, float32 
    compression: str = 'DEFLATE'# DEFLATE, LZW 
    tiled: bool = True          # create tiled geotiff, faster reads 
    overview_levels: Union[List[int], str] = 'AUTO' 
    nodata: Optional[float] = None 
    preserve_bounds: bool = False # if true preserve original bounds exactly 


    def help(self) -> Dict[str,Any]: 
        help_dict = { 
                
                     "target resolution" : "desired resolution of output",
                     "scale factor" : "scale factor ",
                     "resampling": "choose from nearest, bilinear. cubic, average",
                     "dtype": "byte, float32",
                     "compression": "DEFLATE, LZW",
                     "tiled": "create tiled geotiff",    
                }
        return help_dict 
    def print_table(self) -> None:
        cols = ["downsampling param","value"]
        rows = [ 
                ["uris",len(self.uris)],
                ["destination",str(self.out_dir)],
                ["target res", str(self.target_resolution if self.target_resolution else "")],
                ["scale factor",str(self.scale_factor if self.scale_factor else "")],
                ["target w", str(self.target_width if self.target_width else "")],
                ["target h", str(self.target_height if self.target_height else "")],
                ["resampling method", self.resampling],
                ["dtype", self.dtype if self.dtype else ""],
                ["compression", self.compression],
                ["tiled", self.tiled],
                ["overview levels", str(self.overview_levels)],
                ["nodata", str(self.nodata if self.nodata else "")],
                ["preserve bounds", self.preserve_bounds]
                ]
        face.table(cols, rows)

        



def downsample_dir(source: str, out_path: Path) -> Path: 
    dest = Path(out_path) / f"{gen_uuid_from_str(source)}"  
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"browse-{gen_uuid_from_str(source)}"
    return out_path


def _add_text_field(layer, name: str, width: int = 128) -> None:
    fd = ogr.FieldDefn(name, ogr.OFTString)
    fd.SetWidth(width)
    layer.CreateField(fd)

def _add_real_field(layer, name: str) -> None:
    fd = ogr.FieldDefn(name, ogr.OFTReal)
    layer.CreateField(fd)

def stage_label_gpkg(gpkg_path: Path, epsg: int | None = None) -> None:
    gpkg_dest = gpkg_path/"path_vectors.gpkg"
    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(gpkg_dest)
    if ds is None:
        raise RuntimeError(f"Could not create GeoPackage: {gpkg_path}")

    srs = None
    if epsg is not None:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)

    path_layer = ds.CreateLayer("damage_path", srs=srs, geom_type=ogr.wkbLineString)
    area_layer = ds.CreateLayer("damage_area", srs=srs, geom_type=ogr.wkbPolygon)

    for lyr in (path_layer, area_layer):
        _add_text_field(lyr, "event_id", 64)
        _add_text_field(lyr, "label", 64)
        _add_real_field(lyr, "confidence")
        _add_text_field(lyr, "notes", 255)

    ds = None

"""
def run_with_gdal_api(source_path: str, params: DSParams) -> None:
    src_ds = gdal.Open(source_path)
    translate_opts = gdal.TranslateOptions(
            outputSRS=None,
            xRes=params.target_resolution[0] if params.target_resolution else 0.0, 
            yRes=params.target_resolution[1] if params.target_resolution else 0.0, 
            width=params.target_width if params.target_width else 0, 
            height=params.target_height if params.target_height else 0, 
            resampleAlg=params.resampling,
            outputType=params.dtype, 
            creationOptions=co_opts, 
            noData=params.nodata 
        )
"""
