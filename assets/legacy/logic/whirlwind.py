import csv
import os
import re
from pathlib import Path
import argparse
from typing import Any, Iterable, List, Dict, Optional
from osgeo import gdal, osr
import argparse
import toolbox


def main(argv: Optional[List[str]]=None) -> int:
    p = argparse.ArgumentParser(description='whirlwind: helps ingest, relate, label, wrangle, ingest, normalize datacubes')
    
    p.add_argument("--datadir","-d",required=True,help="input directory")
    p.add_argument("--output","-o",required=True,help="output csv name")
    p.add_argument("--verbose","-v",default=False,help="verbose output for bugs")
    

    args = p.parse_args(argv)
    toolbox.write_csv_mosaics(args.datadir,args.output)

if __name__ == "__main__":
    raise SystemExit(main())
