"""whirlwind.wrangler.downsample 
    PURPOSE:
        - holds logic for downsampling mosaics 
    BEHAVIOR:
        - using DSParams to hold user configuration, downsample using a subprocess 
        `gdal_translate` command or uses the gdal api to return downsampled geotiff with 
        preserved geodata 

"""



def downsample_mosaic(source_path: str, out_path: str, params: DSParams, subprocess: bool=True) -> int:
    return 999

def build_gdal_subprocess() -> None:
    ... 

def run_with_gdal_api() -> None:
    ...
