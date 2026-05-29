
INIT_DB_HELP = """
usage: database init [options]

purpose:
  Initialize a WHIRLWIND database run by chaining the standard setup commands.

options:
  -f, --force
      Forward force/overwrite behavior to steps that support it.

  -h, --help
      Show this help.

examples:
  database init
  database init -f
""".strip()


from whirlwind.commands.bridge import (
    BridgeCommand,
    RequestBuilder,
    ResultReporter,
    TokenView,
)
from whirlwind.domain.config.schema import Config
from whirlwind.interface import face

from whirlwind.commands.builders.write_id_manifest_cmd import WriteIDManifestCommand
from whirlwind.commands.builders.discover_metadata_cmd import DiscoverMetadataCommand
from whirlwind.commands.builders.build_metamosaics_cmd import BuildMetamosaicCommand
from whirlwind.commands.builders.downsample_cmd import DownsampleCommand
from whirlwind.commands.builders.stage_tesselation_cmd import StageTesselationCommand
from whirlwind.commands.builders.stage_damagepaths_cmd import StagePathsCommand
from whirlwind.bridges.database.init import DatabaseInitBridge, Request, Result, InitStep
# later:
# from whirlwind.commands.builders.sql_init_cmd import SQLInitCommand



class DatabaseInitRequestBuilder(RequestBuilder[Request]):
    def __init__(self, steps: tuple[InitStep, ...]) -> None:
        self.steps = steps

    def help(self) -> str:
        return INIT_DB_HELP
    def from_tokens(
        self,
        tokens: list[str],
        config: Config,
    ) -> Request:
        tv = TokenView.parse(tokens)

        return Request(
            config=config,
            force=tv.has("-f", "--force"),
            steps=self.steps,
        )


class DatabaseInitReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:
        face.header("database init report")

        for step in result.steps:
            if step.code == 0:
                face.info(f"{step.name}: ok")
            else:
                face.error(f"{step.name}: failed with code {step.code}")

        return result.code



DATABASE_INIT_STEPS = (
    InitStep(
        name="manifest",
        command=WriteIDManifestCommand,
    ),
    InitStep(
        name="metadata",
        command=DiscoverMetadataCommand,
        tokens=("--core",),
    ), 
    InitStep(
        name="metamosaics", 
        command=BuildMetamosaicCommand, 
    ),
    InitStep(
        name="downsample",
        command=DownsampleCommand, 
        tokens=("--display",)
    ),
    InitStep(
        name="tiling",
        command=StageTesselationCommand,
    ),
    InitStep(
        name="damage paths",
        command=StagePathsCommand,
    ),
    # InitStep(
    #     name="sql",
    #     command=SQLInitCommand,
    # ),
)


DatabaseInitCommand = BridgeCommand(
    name="init",
    builder=DatabaseInitRequestBuilder(DATABASE_INIT_STEPS),
    bridge=DatabaseInitBridge(),
    reporter=DatabaseInitReporter(),
)

