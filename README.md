# W:HIRLWIND
w:hirlwind is a recursive acronym that also describes its function:
`WHIRLWIND: Helps Ingest, Relate, Label, Wrangle, Index, Normalize Datacubes`
## program overview
the primary goal of w:hirlwind is to serve as a coordinating program between an unorganized drive and a database of datacubes or "metamosaics".
- `unorganized_drive -> ` **whirlwind.py** `-> metamosaic.db`

given an unorganized bucket of rasters, vectors, geotags, etc **w:hirlwind** performs the taks of *INGESTING* these data from the unorganized bucket to local object storage or a cloud bucket, *RELATING* mosaics, vectors, tiles, and other geographic data entities to one another through a "metamosaic" datacube, *LABELING* data with labels to be used in future machine learning tasks, *WRANGLING* the pixels, vector data, and metadata into a regular (i.e. standardized) directory/database convention, providing *INDEXES* for fast lookups, and *NORMALIZING* by reducing redundancy, insuring data integrity, and providing a unique primary key for each metamosaic stack. 
### the idea of a metamosaics
w:hirlwind helps organize geodata using a datacube abstraction, what we will call a *metamosaic*. these *metamosaics* are georeferenced collections of orthomosaics, tiles, vectors, annotations, etc. every metamosaic is confined to a precise spatial footprint over a small temporal period, but two metamosaics might contain a vastly different array of orthomosaics, tiles, and vector data depending on the collection efforts from that footprint. 
![metamosaic](metamosaic.png)
