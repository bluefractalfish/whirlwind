from whirlwind.commands.router import CommandRouter 
from whirlwind.commands.builders.downsample_cmd import DownsampleCommand 
from whirlwind.commands.builders.write_id_manifest_cmd import WriteIDManifestCommand
from whirlwind.commands.builders.discover_metadata_cmd import DiscoverMetadataCommand
from whirlwind.commands.builders.stage_damagepaths_cmd import StagePathsCommand 
from whirlwind.commands.builders.stage_tesselation_cmd import StageTesselationCommand
from whirlwind.commands.builders.tesselate_mosaics_cmd import TesselationCommand 
from whirlwind.commands.builders.export_shards_cmd import ExportShardsCommand
from whirlwind.commands.builders.stitch_tifs_cmd import StitchCommand
from whirlwind.commands.builders.init_database_cmd import DatabaseInitCommand
from whirlwind.commands.builders.build_metamosaics_cmd import BuildMetamosaicCommand

#from whirlwind.commands.fronts.database import DatabaseBuildCommand 

DiscoverOperators = CommandRouter(
        name="discover",
        routes={
            ("","mosaics"): WriteIDManifestCommand, 
            ("meta","metadata"): DiscoverMetadataCommand, 
            }
        )


MetamosaicOperators = CommandRouter(
        name = "mm", 
        routes = {
            ("build", "b"): BuildMetamosaicCommand
            }
        )

MosaicOperators = CommandRouter(
        name="mosaic", 
        routes={
            ("tile","tesselate","t"): TesselationCommand, 
            ("downsample","ds"): DownsampleCommand, 
            }
        )

TileOperators = CommandRouter(
        name="tiles", 
        routes={
            ("export","e"): ExportShardsCommand, 
            ("stitch", "s"): StitchCommand
            }
        )

StagingOperators = CommandRouter(
        name="stage", 
        routes = {
            ("tiles","tiling","t"): StageTesselationCommand, 
            ("paths","p"): StagePathsCommand
            }
        )


DatabaseInitOperator = CommandRouter(
        name="database", 
        routes = {"init": DatabaseInitCommand}
        )

