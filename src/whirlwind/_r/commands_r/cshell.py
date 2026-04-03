from .base import ShellCommand
from whirlwind.tools.pathfinder import find_home_, dir_walker_
import os 

class RestartShell:
    names = ["restart","r"]

    def run(self, tokens) -> int:
        """replace current instance of app with new instance """ 
        try:
            os.execvp("W", ["W"])
        except:
            return 1
    def help(self) -> dict[str,str]:
        return {"restart":"restart current instance by replacing with new one"} 

class QuitShell:
    names = ["quit","q"]

    def run(self, tokens,) -> int:
        ln = input("are you sure you want to quit? (y/n) ")
        if ln != "n":
            return 13 
        else:
            return 0

    def help(self) -> dict[str,str]:
        return {"quit":"safely quit shell"}

class List:
    names = ["list","ls"]

    def run(self, tokens) -> int:
        if len(tokens) != 1:
            print("usage: unexpected tokens")
            return 3
        target = tokens[0]
        match target:
            case "meta" | "metadata" | "m":
                return self.list_metadata()
            case "artifacts" | "art" | "a":
                return self.list_artifacts()
        return 0
    
    def list_metadata(self) -> int: 
        meta_dir = find_home_() / "metadata"

        if not meta_dir.exists():
            print("cannot find metadata directory")
            return 3 
        if not meta_dir.is_dir():
            print(f"not a directory: {meta_dir}")
            return 3

        entries = dir_walker_(meta_dir)        

        if not entries:
            print(f"{meta_dir} is empty")
            return 3 
        for path in entries:
            suf = "/" if path.is_dir() else ""
            print(f"{path.name}{suf}")
        return 0

    def list_artifacts(self) -> int: 
        
        art_dir = find_home_() / "artifacts"

        if not art_dir.exists():
            print("cannot find artifact directory")
            return 3 
        if not art_dir.is_dir():
            print(f"not a directory: {art_dir}")
            return 3

        entries = dir_walker_(art_dir)        

        if not entries:
            print(f"{art_dir} is empty")
            return 3 
        for path in entries:
            suf = "/" if path.is_dir() else ""
            print(f"{path.name}{suf}")
        return 0
