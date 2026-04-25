
from typing import Iterator, Any, Iterable 
from pathlib import Path 
import json 
import csv 


from dataclasses import dataclass, asdict, fields
from whirlwind.interfaces.geo.damagepath import PathPlan, DamagePathPlanner
from whirlwind.specs.path import PathSpec
from whirlwind.filetrees import RunTree, MosaicBranch
from whirlwind.manifests import IDManifest 
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from whirlwind.ui import face 
from whirlwind.interfaces.geo.windows import WindowPlan 
from whirlwind.filetrees.files import RasterFile
from whirlwind.io.planio import TilePlanIO, PlanRow 



class PathPlanRequest:
    def __init__(self, tokens: list[str], config: Config) -> None:
        self.tree = RunTree.from_config(config) 
        self.manifest = IDManifest.from_tree(self.tree) 
        self._paths = self.manifest.get_paths() 

    @property 
    def paths(self) -> Iterator[Path]:
        return self._paths 

class BuildPathPlan(Command):
    name = "plan path"

    def run(self, tokens: list[str], config: Config) -> int:
        
        request = PathPlanRequest(tokens, config)
        
        paths = request.paths 

        for p in paths:
            f = RasterFile(p, georefs=True)
            mosaic_id = f.fid.uid 
            branch = MosaicBranch.plant(request.tree.root, mosaic_id).ensure()
            plan = PathPlan.from_browse(branch, crs_wkt=f.crs_wkt)
            DamagePathPlanner.make_plan(plan, overwrite=True)


        return 0 
        

