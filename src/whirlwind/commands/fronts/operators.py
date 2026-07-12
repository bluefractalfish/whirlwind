from whirlwind.commands.base import Command
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

BuildOperators = CommandRouter(
        name = "make", 
        aliases= ("b",),
        routes={
            ("m", "manifest"): WriteIDManifestCommand, 
            ("md", "meta"): DiscoverMetadataCommand,
            ("mm", "metamosaics"): BuildMetamosaicCommand,
            ("tp", "tileplan"): StageTesselationCommand, 
            ("gp", "geopackages"): StagePathsCommand
            }
        )

ShardOperators = CommandRouter(
        name = "shards", 
        aliases = ("s", ), 
        routes = {
            ("tt", "totiff"): ExportShardsCommand, 
            ("st", "stitch"): StitchCommand, 
            }
        )

RunOperators = CommandRouter(
        name = "run", 
        routes = {
            ("tp", "tileplan"): TesselationCommand, 
            ("ds", "downsample"): DownsampleCommand
            }
        )

DiscoverOperators = CommandRouter(
        name="discover",
        routes={
            ("","mosaics"): WriteIDManifestCommand, 
            ("meta","metadata"): DiscoverMetadataCommand, 
            }
        )


MetamosaicOperators = CommandRouter(
        name = "metamosaic", 
        aliases=("mm",),
        routes = {
            ("build", "b"): BuildMetamosaicCommand
            }
        )


MosaicOperators = CommandRouter(
        name="mosaic", 
        aliases=("m",),
        routes={
            ("tile","tesselate","t"): TesselationCommand, 
            ("downsample","ds"): DownsampleCommand, 
            }
        )

TileOperators = CommandRouter(
        name="tiles", 
        aliases=("t",),
        routes={
            ("export","e"): ExportShardsCommand, 
            ("stitch", "s"): StitchCommand
            }
        )

StagingOperators = CommandRouter(
        name="stage", 
        aliases=("s",),
        routes = {
            ("tiles","tiling","t"): StageTesselationCommand, 
            ("paths","p"): StagePathsCommand
            }
        )


DatabaseInitOperator = CommandRouter(
        name="database", 
        aliases=("db",),
        routes = {"init": DatabaseInitCommand}
        )

