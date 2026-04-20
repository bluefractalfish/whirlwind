# Core Proto Concepts 

concepts with the most general operational principles 

# SpatialGeometry 
    - purpose: anything that references a spatial entity 
    - state: 
        - has footprint 
        - has crs 
        - has transform 
        - has pixel resolution
        - has nodata 
    - actions:
        - record 
        - intersects 
        - transform
    - operational principles: 
        - is instantiated with FootPrint and CRS 
        - intersects(other SpatialGeometry) -> true/false 
# Raster
    - purpose: anything that can be represented as an array of pixel values 
    - states: 
        - has shape (x,y,b)
        - has dtype 
        - has dimensional semantics (what is x,y,b)
    - actions:
        - read full array 
        - read a window 
        - inspect bands 
        - (report layout?)
        - report number of dimensions (3 if x,y,b)
        - quantize 



# ProtoIO 
    - purpose: holds input_uri and output_uri 
    - state:
        - input_uri 
        - output_uri 
    - actions: 
        - make directory 
        - move to directory 

# ProtoParam 
    - extends ProtoIO 
    - purpose: based upon user intent and config file, holds operation params 
    - state: 
        -  operation params 
    - actions build_params: 
        - returns dictionary of param / value 
        - print to user to show config settings 


MAYBE? 
# ProtoOperation 
    - purpose: takes user/config input and changes states of Geometry, Rasters, Filsystem 
    - states: 
        - command 
        - minute 
        - 



