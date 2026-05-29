
import shlex
from collections.abc import Iterable
from typing import Any

from whirlwind.commands.context import CommandContext
from whirlwind.commands.shell.shell_nav_cmds import _records


class CompletionMixin:
    app: Any

    # ------------------------------------------------------------------
    # Completion helpers
    # ------------------------------------------------------------------

    def _ctx(self) -> CommandContext:
        return CommandContext(self.app.config)

    def _tokens_before_completion(
        self,
        line: str,
        begidx: int,
    ) -> list[str]:
        try:
            return shlex.split(line[:begidx])
        except ValueError:
            return line[:begidx].split()

    @staticmethod
    def _match(text: str, choices: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []

        for choice in choices:
            if not choice:
                continue
            if choice in seen:
                continue
            if choice.startswith(text):
                seen.add(choice)
                out.append(choice)

        return sorted(out)

    def _all_records(self):
        try:
            return _records(self._ctx())
        except Exception:
            return []

    def _metamosaic_ids(self) -> list[str]:
        return sorted(
            {
                str(record.metamosaic_id)
                for record in self._all_records()
                if record.metamosaic_id
            }
        )

    def _mosaic_ids(self) -> list[str]:
        return sorted(
            {
                str(record.mosaic_id)
                for record in self._all_records()
                if record.mosaic_id
            }
        )

    def _known_scope_ids(self) -> list[str]:
        return [*self._metamosaic_ids(), *self._mosaic_ids()]

    def _run_ids(self) -> list[str]:
        try:
            ctx = self._ctx()
            return sorted(
                path.name
                for path in ctx.dest_dir.iterdir()
                if path.is_dir()
            )
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Navigation completion
    # ------------------------------------------------------------------

    def complete_ls(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(
            text,
            [
                "scope",
                ".",
                "mm",
                "metamosaic",
                "metamosaics",
                "m",
                "mosaic",
                "mosaics",
                "meta",
                "metadata",
                "cols",
                "columns",
                "files",
                "tree",
            ],
        )

    def complete_cd(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        tokens = self._tokens_before_completion(line, begidx)
        args = tokens[1:] if tokens and tokens[0] == "cd" else tokens

        if not args:
            return self._match(
                text,
                [
                    "/",
                    "..",
                    "root",
                    "mm",
                    "metamosaic",
                    "m",
                    "mosaic",
                    *self._known_scope_ids(),
                ],
            )

        first = args[0]

        if first in ("mm", "metamosaic") and len(args) == 1:
            return self._match(text, self._metamosaic_ids())

        if first in ("m", "mosaic") and len(args) == 1:
            return self._match(text, self._mosaic_ids())

        return []

    def complete_env(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        tokens = self._tokens_before_completion(line, begidx)
        args = tokens[1:] if tokens and tokens[0] == "env" else tokens

        if not args:
            return self._match(
                text,
                [
                    "run_id",
                    "run",
                    "dry",
                    "dry_run",
                    "dry-run",
                    "quiet",
                    "q",
                ],
            )

        key = args[0]

        if key in ("dry", "dry_run", "dry-run", "quiet", "q") and len(args) == 1:
            return self._match(
                text,
                [
                    "on",
                    "off",
                    "true",
                    "false",
                    "yes",
                    "no",
                    "1",
                    "0",
                ],
            )

        if key in ("run_id", "run") and len(args) == 1:
            return self._match(text, self._run_ids())

        return []

    def complete_view(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(
            text,
            [
                "browse",
                "tiles",
                "shards",
                "metadata",
            ],
        )

    # ------------------------------------------------------------------
    # Operator completion
    # ------------------------------------------------------------------

    def complete_discover(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(text, ["mosaics", "meta", "metadata"])

    def complete_mosaic(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(
            text,
            [
                "downsample",
                "ds",
                "tile",
                "tesselate",
                "t",
            ],
        )

    def complete_tiles(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(text, ["export", "e", "stitch", "s"])

    def complete_stage(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(text, ["tiles", "tiling", "t", "paths", "p"])

    def complete_database(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(text, ["init"])

    def complete_metamosaic(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self._match(text, ["build", "b"])

    def complete_mm(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        return self.complete_metamosaic(text, line, begidx, endidx)
