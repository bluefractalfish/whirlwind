"""whirlwind.commands.catalog

PURPOSE: 
    - entrypoint for catalog command 
BEHAVIOR:
    - catalog build: creates a catalog of mosaics with uri uuid table and basic size/dim data 
    - catalog build ... -> creates run_id/metadata/catalog.csv from mnt/ if args = ... 
    - catalog build path/to/mosaics -> creates run_id/metadata/catalog.csv          

    - catalog stats: creates metadata csv of mosaics (legacy `inspect`)
    - catalog stats ... -> creates run_id/metadata/metadata.csv from mnt/
    - catalog stats path/to/mosaics -> creates from path/to/mosaics 

    - catalog validate: for validating after projection, sampling, downsampling 
"""



from .base import Command



class CatalogCommand(Command):
    name = "catalog"

    
