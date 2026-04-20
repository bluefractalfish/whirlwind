
from typing import Iterator, Any, Iterable 
from pathlib import Path 
import json 
import csv 


from dataclasses import dataclass, asdict, fields
from whirlwind.specs import TSpec 
from whirlwind.filetrees import RunTree, MosaicBranch
from whirlwind.manifests import IDManifest 
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from whirlwind.ui import face 
from whirlwind.interfaces.geo.windows import WindowPlan 
from whirlwind.filetrees.files import RasterFile
from whirlwind.io.planio import TilePlanIO, PlanRow 


class TesselationPlan(Command):
    name = "plan"

    manifest: IDManifest 
    tree: RunTree 
    spec: TSpec


    def run(self, tokens: list[str], config: Config) -> int:
        
        face.prog_row("1/3", "constructing specs from config")
        self.spec = TSpec.from_config(config) 
        
        face.prog_row("2/3", "finding run tree and manifest")
        self.tree = RunTree.from_config(config)
        self.manifest = IDManifest.from_tree(self.tree)
        
        face.prog_row("3/3", "writing plan")
        paths = self.manifest.get_paths()
        for p in paths:
            mosaic_id = RasterFile(p).fid.uid 
            branch = MosaicBranch.plant(self.tree.root, mosaic_id).ensure()
            planio = TilePlanIO(branch, self.spec)
            reader = WindowPlan(p, self.spec)

            for ri, ci, x, y, h, w in reader.get_grid():
                row = PlanRow(row_i=ri, col_i=ci, 
                              x=x, y=y, w=w, h=h)
                planio.append_csv(row)

        return 0 
        

