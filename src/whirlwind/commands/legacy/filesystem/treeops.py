from dataclasses import dataclass 
from whirlwind.filetrees import RunTree, MosaicBranch
from whirlwind.commands.base import Command 
from whirlwind.domain.config import Config 

class BuildTree(Command):
    name = "build tree"
    tree: RunTree 

    def run(self, tokens: list[str], config: Config) -> int: 

        if len(tokens) == 0:
            run_id = config.run_id()
        elif len(tokens) == 1:
            run_id = str(tokens[0])

        out_root = config.out_path() / run_id 
        self.tree = RunTree.plant(out_root)

        return 0
 
    def get_tree(self) -> "RunTree":
        return self.tree
    
    def plant_and_get(self, tokens: list[str], config: Config) -> "RunTree":
        """ plants tree from config.out_path and plants, returning planted tree  """ 
        out_root = config.out_path() 
        self.tree = RunTree.plant(out_root)
        return self.tree

class CutTree(Command):
    name = "delete tree"

    def run(self, tokens: list[str], config: Config) -> int:

        if len(tokens) == 0:
            run_id = config.run_id()
        elif len(tokens) == 1:
            run_id = str(tokens[0])

        out_root = config.out_path() / run_id 
        tree = RunTree.plant(out_root)

        confirm = input(f"are you sure you want to prune the tree with root: {out_root}? (y/n) ")
        if confirm == "y":
            tree.recursive_prune()
            return 0 
        else:
            return 1



