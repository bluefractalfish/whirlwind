""" whirlwind.commands.label.build 

PURPOSE: 
    - given precomputed path geometry output tile label metadata

BEHAVIOR:
    - given tiling specs, path geometry, CRS policy, compute for each tile:

        - tile_id
        - row_id / col_id
        - source_uri
        - footprint polygon
        - intersects_path: bool
        - intersects_area: bool
        - label: damage / no_damage / ambiguous / etc.
        - maybe overlap_fraction
        - maybe distance_to_path
    - DOES NOT READ RASTER BANDS, only does math in metric space 
PUBLIC:
    - BuildLabelCommand 
    - label build

"""



