from typing import List
from typing_extensions import Dict
from whirlwind.filesystem.files import FileID 
from pathlib import Path 
from whirlwind.interface.interface import Interface 

interface = Interface() 

def test_hash_on(directory: str):

    pathlist = Path(directory).rglob("*.tif") 
    for path in pathlist: 
        hashed = FileID.mosaic(path) 
        print(path.as_uri() + "\n" + hashed)
    
