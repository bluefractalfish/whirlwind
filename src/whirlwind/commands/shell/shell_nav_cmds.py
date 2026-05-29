import csv 
import os 
import subprocess 

from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.commands.base import Command 
from whirlwind.commands.bridge import TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.domain.config import Config
from whirlwind.interface import face


def _manifest(ctx: CommandContext) -> IDManifest:
    return IDManifest(ctx.run_tree.get_manifest_path_csv("manifest.csv"))

def _records(ctx: CommandContext):
    manifest = _manifest(ctx) 

    if not manifest.exists():
        return []

    return list(manifest.records())

def _scoped_records(ctx: CommandContext):
    records = _records(ctx)
    scope = ctx.scope 

    if scope.kind == "root":
        return records

    if scope.kind == "metamosaic":
        return [
            record
            for record in records
            if record.metamosaic_id == scope.metamosaic_id
        ]

    if scope.kind == "mosaic":
        return [
            record
            for record in records
            if record.mosaic_id == scope.mosaic_id
        ]

    return records


class CdCommand(Command):
    name = "cd"

    def run(self, tokens: list[str], config: Config) -> int:
        ctx = CommandContext(config)
        tv = TokenView.parse(tokens)

        target = tv.arg(0)

        if target in (None, "/", "root"):
            ctx.scope.clear()
            face.info("scope: /")
            return 0

        if target in ("mm", "metamosaic"):
            mm_id = tv.require(1, "metamosaic_id")
            ctx.scope.cd_metamosaic(mm_id)
            face.info(f"scope: {ctx.scope.working_dir()}")
            return 0

        if target in ("m", "mosaic"):
            mosaic_id = tv.require(1, "mosaic_id")
            mm_id = None

            for record in _records(ctx):
                if record.mosaic_id == mosaic_id:
                    mm_id = record.metamosaic_id
                    break

            ctx.scope.cd_mosaic(mosaic_id, metamosaic_id=mm_id)
            face.info(f"scope: {ctx.scope.working_dir()}")
            return 0

        if target == "..":
            if ctx.scope.kind == "mosaic" and ctx.scope.metamosaic_id:
                ctx.scope.cd_metamosaic(ctx.scope.metamosaic_id)
            else:
                ctx.scope.clear()

            face.info(f"scope: {ctx.scope.working_dir()}")
            return 0

        # Convenience: allow `cd <known_id>`.
        for record in _records(ctx):
            if record.mosaic_id == target:
                ctx.scope.cd_mosaic(record.mosaic_id, record.metamosaic_id)
                face.info(f"scope: {ctx.scope.working_dir()}")
                return 0

            if record.metamosaic_id == target:
                ctx.scope.cd_metamosaic(str(record.metamosaic_id))
                face.info(f"scope: {ctx.scope.working_dir()}")
                return 0

        face.error(f"unknown scope target: {target}")
        return 3


class SetCommand(Command):
    name = "set"

    def run(self, tokens: list[str], config: Config) -> int:
        ctx = CommandContext(config)
        tv = TokenView.parse(tokens)

        key = tv.arg(0)
        value = tv.arg(1)

        if key is None:
            rows = [
                ["run_id", ctx.run_id],
                ["scope", ctx.scope.working_dir()],
                ["dry", str(ctx.session.settings.dry_run)],
                ["quiet", str(ctx.session.settings.quiet)],
            ]
            face.table(["key", "value"], rows, title="session")
            return 0

        if value is None:
            face.error("usage: set <key> <value>")
            return 3

        match key:
            case "run_id" | "run":
                config.merged.setdefault("global", {})["run_id"] = value
                face.info(f"run_id: {value}")
                return 0

            case "dry" | "dry_run" | "dry-run":
                ctx.session.settings.dry_run = value.lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                face.info(f"dry_run: {ctx.session.settings.dry_run}")
                return 0

            case "quiet" | "q":
                ctx.session.settings.quiet = value.lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                face.info(f"quiet: {ctx.session.settings.quiet}")
                return 0

            case _:
                face.error(f"unknown setting: {key}")
                face.info("available: run_id, dry, quiet")
                return 3


class LsCommand(Command):
    name = "ls"

    def run(self, tokens: list[str], config: Config) -> int:
        ctx = CommandContext(config)
        tv = TokenView.parse(tokens)
        what = tv.arg(0, "scope")

        if what in ("scope", "."):
            face.info(f"run: {ctx.run_tree.root}")
            face.info(f"scope: {ctx.scope.working_dir()}")
            face.info(f"dry: {ctx.session.settings.dry_run}")
            face.info(f"quiet: {ctx.session.settings.quiet}")
            return 0

        if what in ("mm", "metamosaic", "metamosaics"):
            counts: dict[str, int] = {}

            for record in _records(ctx):
                if record.metamosaic_id:
                    counts[record.metamosaic_id] = (
                        counts.get(record.metamosaic_id, 0) + 1
                    )

            rows = [
                [metamosaic_id, str(n)]
                for metamosaic_id, n in sorted(counts.items())
            ]

            face.table(
                ["metamosaic_id", "mosaics"],
                rows,
                title="metamosaics",
            )
            return 0

        if what in ("m", "mosaic", "mosaics"):
            rows = [
                [
                    record.mosaic_id,
                    record.metamosaic_id or "",
                    record.date,
                    record.variant_id,
                    str(record.path),
                ]
                for record in _scoped_records(ctx)
            ]

            face.table(
                ["mosaic_id", "metamosaic_id", "date", "variant", "path"],
                rows,
                title="mosaics",
            )
            return 0

        if what in ("meta", "metadata", "cols", "columns"):
            rows = []

            for csv_path in sorted(ctx.run_tree.manifest_dir.glob("*.csv")):
                with csv_path.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    cols = reader.fieldnames or []

                rows.append([csv_path.name, ", ".join(cols)])

            face.table(["file", "columns"], rows, title="metadata columns")
            return 0

        if what in ("files", "tree"):
            rows = []

            for path in sorted(ctx.run_tree.root.rglob("*")):
                if path.is_file():
                    rows.append(
                        [
                            str(path.relative_to(ctx.run_tree.root)),
                            str(path.stat().st_size),
                        ]
                    )

            face.table(["path", "bytes"], rows, title="files")
            return 0

        face.error(f"unknown ls target: {what}")
        face.info("available: scope, mm, mosaics, metadata, files")
        return 3


class ViewCommand(Command):
    name = "view"

    def run(self, tokens: list[str], config: Config) -> int:
        ctx = CommandContext(config)
        tv = TokenView.parse(tokens)
        what = tv.arg(0, "browse")

        records = _scoped_records(ctx)

        if not records:
            face.warning("nothing in active scope")
            return 1

        viewer = os.environ.get("WW_VIEWER", "xdg-open")
        opened = 0

        for record in records:
            branch = ctx.run_tree.branch_for(record)

            match what:
                case "browse":
                    candidates = (
                        list(branch.browse_dir.glob("*.tif"))
                        + list(branch.browse_dir.glob("*.tiff"))
                    )

                case "tiles":
                    candidates = list(branch.tiles_dir.glob("*"))

                case "shards":
                    candidates = list(branch.shards_dir.glob("*.tar"))

                case "metadata":
                    candidates = list(branch.metadata_dir.glob("*"))

                case _:
                    face.error(f"unknown view target: {what}")
                    face.info("available: browse, tiles, shards, metadata")
                    return 3

            for path in candidates:
                subprocess.Popen([viewer, str(path)])
                face.info(f"opened: {path}")
                opened += 1

        return 0 if opened else 1

