## CHANGE MOSAIC ID/ FILE ID POLICIES 

    - mosaic naming is still embedded in RasterFIle 
            - self.raster_id = raster_file_id(self.path)
            where 
            - file_id 
            - mosaic_id 
            - mid 
            all return that value 
    - CHANGE 
            - make RasterFile call explicity ID policy: 
               
               self.raster_id=FileID.mosaic(self.path) 
        
        make FileID own all id schema functions so future naming changes come from FileID only 
    `` class FileID: 
            ID_SCHEME = "id_scheme_v2"
            ID_VERSION = 2 

            def mosaic(path|str) -> str 
                    M-variant-hash

            def metamosaic(member_ids) -> str 

            def branch(mosaic_id: str) -> str 
                return mosaic_id 

            def tile(mosaic_id, row_i, col_i) -> str 

            def shard(branch, index) -> str 


## IDManifest does not have stable mosaic-record model 
    - IDManifest.write_from() discovers raster files and writes file.record()
        - file.record writes:
            - file_id 
            - date 
            - variant 
            - variant_type 
            - spectral_id 
            - uri 
            - path 
        - IDManifest.ids() reads from ids, mids() from mids, etc 

    CHANGE 
        - standardize manifest around: 
            - mosaic_id 
            - source_uri 
            - path 
            - date 
            - variant_id 
            - variant_type 
            - spectral_id 
            - id_scheme 
            - id_version 
        - IDManifest.ids() reads mosaic_id not id 
        - remove file_id 
        - remove all mid references 

        
## branch layout is hardcoded as root / file id 
    - RunTree.plant_mosaic_branch(file_id) calls plant(self.root, file_id)

        - downstream assumes mosaic is at runtree.root 

    CHANGE 
        - add methods to runtree: 
            - tree.branch_for(mosaic_id)
            - tree.metamosaic_tree(metamosaic_id)
            - tree.branch_for(mosaic_id, metamosaic_id=...)
        - MAKE RUNTREE LAYOUT DRIVEN: 
            - make RunTreeLayout class 
            - do not make bridge code know whether branches are under root 
                or under metamosaic directory. only runtreelayout knows that 
## change bridges to accept MosaicRecord objects, not raw paths: 
    - change anything like: 
        - f = RasterFile(p)
        - fid=f.file_id 
        - branch = MosaicBranch.plant.... 
    
    - create MosaicRecord: 
        - mosaic_id 
        - metamosaic 
        - path 
        - source 
        - date 
        - variant 
        - 
        .... 
    
    - currently, 
        IDManifest.paths()
         -> Path 
         -> RasterFIle(Path)
         -> FileID 
         -> MosaicBranch.plant... 
    - change to: 
        - IDManifest.records()
            - MosaicRecord 
            - RunTree.branch_for(record)
            - operation(record branch)

        - allows for single mosaic op, selected, all, one metamosaic....
## CHange TokenView to accept key-value flags 

    - allow for test tileplan --mosaic=m-...

    - Add Selector layer 
        - MosaicSelection: 
            - mosaic_ids: tuple 
            - variants: tuple 
            - dates 
            - metamosaic_ids 
            - limit? 
        - MosaicSelectionBuilder: 
            - from_tokens -> MosaicSelection 


## BUILD METAMOSAICS 

1. Read MosaicRecord rows from current root manifest.
2. Filter by selector if provided.
3. Load or compute footprints for each mosaic.
4. Build overlap graph:
   - node = mosaic_id
   - edge = footprints intersect
5. Connected components become metamosaics.
6. Generate metamosaic_id using FileID.metamosaic(sorted(member_ids)).
7. Create:
   runtree/metamosaics/<metamosaic_id>/
   runtree/metamosaics/<metamosaic_id>/branches/
   runtree/metamosaics/<metamosaic_id>/manifest/
8. Move/copy/link existing MosaicBranch dirs into the metamosaic tree.
9. Write metamosaic manifest.
10. Regenerate root manifest.
