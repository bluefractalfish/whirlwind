BUILD_METAMOSAIC_HELP = """
build metamosaic

Purpose:
  Build metamosaic membership from raster metadata footprints.

Behavior:
  - Reads the root mosaic manifest.
  - Reads core metadata containing WGS84 footprint/bbox fields.
  - Computes footprint intersections.
  - Assigns metamosaic_id to overlapping mosaic groups.
  - Rewrites the root manifest with metamosaic_id and branch_id fields.
  - Plants metamosaic directory branches under the current RunTree.

Usage:
   metamosaics build [options]
   mm build [options]

Examples:
  metamosaic build
  mm build 
  metamosaic build --stem=denver
  metamosaic build --metadata=core-metadata.csv
  metamosaic build --stem=clearlake --metadata=core-metadata.csv -f

Options:
  --stem=<name>
      Human-readable stem used in generated metamosaic IDs.

      Example:
        --stem=denver

      Output ID shape:
        MM-denver-<hash>

  --metadata=<file>
      Metadata CSV name inside the run manifest directory.

      Default:
        core-metadata.csv

      Expected path:
        <run_tree>/manifest/core-metadata.csv

  -f, --force
      Allow rebuild/overwrite behavior where supported.

Required input files:
  <run_tree>/manifest/manifest.csv
      Root mosaic manifest. Usually created by:
        test ids ./mnt -f

  <run_tree>/manifest/core-metadata.csv
      Core metadata with footprint fields. Usually created by:
        test meta --core -f

Required metadata columns:
  mosaic_id
  minx_wgs84
  miny_wgs84
  maxx_wgs84
  maxy_wgs84

Recommended metadata columns:
  path
  source_uri
  footprint_wgs84
  crs_wkt
  srid
  transform

Outputs:
  <run_tree>/manifest/manifest.csv
      Rewritten with:
        metamosaic_id
        branch_id

  <run_tree>/manifest/metamosaic.csv
      Metamosaic membership table.

  <run_tree>/manifest/metamosaic-intersections.csv
      Direct mosaic overlap pairs.

  <run_tree>/metamosaics/<metamosaic_id>/branches/<mosaic_id>/
      Branches for mosaics assigned to a metamosaic.

  <run_tree>/mosaics/<mosaic_id>/
      Branches for mosaics not assigned to a metamosaic.

Notes:
  - Intersection is based on WGS84 bbox fields.
  - Mosaics with missing footprint fields are skipped from metamosaic grouping.
  - Singleton mosaics can remain loose unless you intentionally assign every mosaic to a one-member metamosaic.
"""

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.bridges.catalogs.buildmetamosaics import (
    BuildMetamosaicBridge,
    Request,
    Result,
)
from whirlwind.commands.bridge import (
    BridgeCommand,
    RequestBuilder,
    ResultReporter,
    TokenView,
)
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config
from whirlwind.interface import face


class BuildMetamosaicRequest(RequestBuilder[Request]):
    def from_tokens(self, tokens: list[str], config: Config) -> Request:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        cfg = ctx.section("metamosaic", "build")

        metadata_name = tv.value(
            "--metadata",
            str(cfg.get("metadata_name", "core-metadata.csv")),
        ) or "core-metadata.csv"

        stem = tv.value("--stem", str(cfg.get("stem", "locale"))) or "locale"

        root_manifest_name = str(cfg.get("root_manifest_name", "manifest.csv"))
        metamosaic_manifest_name = str(
            cfg.get("manifest_name", "metamosaic.csv")
        )

        summary_name = cfg.get("summary_name", "metamosaic_summary.csv")

        manifest = IDManifest(
            ctx.run_tree.get_manifest_path_csv(root_manifest_name)
        )

        return Request(
            run_tree=ctx.run_tree,
            manifest=manifest,
            metadata_path=ctx.run_tree.manifest_dir / metadata_name ,
            stem=stem,
            metamosaic_manifest_name=metamosaic_manifest_name,
            metamosaic_summary_name=summary_name, 
            root_manifest_name=root_manifest_name,
            force=tv.has("-f", "--force"),
        )

    def help(self) -> str: 
        return BUILD_METAMOSAIC_HELP





class BuildMetamosaicReporter(ResultReporter[Result]):
    def report(self, result: Result) -> int:

        face.info(f"metamosaic manifest: {result.metamosaic_manifest_path}")
        face.info(f"root manifest: {result.root_manifest_path}")
        face.info(f"mosaics seen: {result.mosaics_seen}")
        face.info(f"intersections: {result.intersections}")
        face.info(f"metamosaics written: {result.metamosaics_written}")

        columns = [
            "metamosaic_id",
            "n",
            "patch",
            "members",
        ]

        rows = [
            [
                s.n_mosaics,
                face.print_bbox(
                    minx=s.minx_wgs84,
                    miny=s.miny_wgs84,
                    maxx=s.maxx_wgs84,
                    maxy=s.maxy_wgs84,
                    title=s.metamosaic_id,
                ),

                self._members_preview(s.members),
            ]
            for s in result.summaries
        ]

        if rows:
            face.table(columns, rows, title="metamosaics")
        else:
            face.warning("no metamosaic groups written")

        return result.code

    def _members_preview(self, members: tuple[str, ...], limit: int = 10) -> str:
        if len(members) <= limit:
            return ", ".join(members)

        shown = ", ".join(members[:limit])
        return f"{shown}, +{len(members) - limit} more"


BuildMetamosaicCommand = BridgeCommand(
    name="build metamosaic",
    builder=BuildMetamosaicRequest(),
    bridge=BuildMetamosaicBridge(),
    reporter=BuildMetamosaicReporter(),
)
