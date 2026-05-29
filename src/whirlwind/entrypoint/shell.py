from __future__ import annotations

import os
import shlex

import cmd2

from collections.abc import Iterable 
from whirlwind.commands.context import CommandContext
from whirlwind.commands.shell.shell_nav_cmds import _records 
from whirlwind.commands.shell.autocomplete import CompletionMixin
from whirlwind.entrypoint.app import WhirlwindApp


class WShell(CompletionMixin, cmd2.Cmd):

    def __init__(self, app: WhirlwindApp) -> None:
        super().__init__(
            allow_cli_args=False,
            persistent_history_file=".whirlwind_history",
        )
        self.app = app
        self.exit_code = 0
        # Keep cmd2 from treating unknown input as OS shell commands.
        self.default_to_shell = False 

        run_id = getattr(app, "run_id", "dev")

        self.intro = (
                "WHIRLWIND SHELL \n"
                "type help or ? for list of commands \n"
                f"run_id: {run_id}"
        )

        self._refresh_prompt()

    def run(self) -> int:
        self.cmdloop()
        return self.exit_code

    def _refresh_prompt(self) -> None:
        try: 
            scope = self.app.config.session.scope.working_dir()
        except Exception: 
            scope = "/"
        self.prompt = f"[{scope}] "

    def _run_app(self, tokens: list[str]) -> None: 
        try: 
            ret_code = self.app.run(tokens)
        except Exception: 
            raise 
        finally: 
            self._refresh_prompt()

        self.exit_code = ret_code 
        
        match ret_code: 
            case 0: 
                return 
            case 3: 
                self.perror("usage: error")
            case 11:
                self.perror("usage: unrecognized command")
            case 13: 
                self.exit_code = 13 
                self._should_quit = True 
            case _:
                self.perror(f"command failed with code: {ret_code}")

    def _dispatch(self, head: str, statement: cmd2.Statement) -> None: 
        try: 
            args = shlex.split(statement.args)
        except ValueError as exc: 
            self.perror(f"token parse error: {exc}")
            self.exit_cide = 3 
            return 

        self._run_app([head, *args])

    def default(self, statement: cmd2.Statement) -> None:

        line = statement.raw.strip()
        if not line:
            return

        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            self.perror(f"token parse error: {exc}")
            self.exit_code = 3
            return
        
        self._run_app(tokens)

    @cmd2.with_category("Whirlwind navigation")
    def do_ls(self, statement: cmd2.Statement) -> None:
        """List active run resources."""
        self._dispatch("ls", statement)

    def help_ls(self) -> None:
        self.poutput(
            """
usage:
  ls
  ls scope
  ls mm
  ls metamosaics
  ls mosaics
  ls metadata
  ls files

examples:
  ls
  ls mm
  ls mosaics
  ls metadata
"""
        )

    @cmd2.with_category("Whirlwind navigation")
    def do_cd(self, statement: cmd2.Statement) -> None:
        """Change active Whirlwind scope."""
        self._dispatch("cd", statement)

    def help_cd(self) -> None:
        self.poutput(
            """
usage:
  cd /
  cd ..
  cd mm <metamosaic_id>
  cd metamosaic <metamosaic_id>
  cd mosaic <mosaic_id>
  cd <known_id>

examples:
  cd /
  cd mm MM-denver-a91f2c
  cd mosaic M-240119-DSM-a31f
  cd ..
"""
        )

    @cmd2.with_category("Whirlwind navigation")
    def do_env(self, statement: cmd2.Statement) -> None:
        """Show or update shell session settings."""
        self._dispatch("env", statement)

    def help_env(self) -> None:
        self.poutput(
            """
usage:
 env 
 env  run_id <id>
 env  dry on|off
 env  quiet on|off

examples:
  env
  env run_id tornado-test
  env dry on
  env quiet off
"""
        )

    @cmd2.with_category("Whirlwind navigation")
    def do_view(self, statement: cmd2.Statement) -> None:
        """Open browse rasters, tiles, shards, or metadata from the active scope."""
        self._dispatch("view", statement)

    def help_view(self) -> None:
        self.poutput(
            """
usage:
  view browse
  view tiles
  view shards
  view metadata

examples:
  view browse
  view shards
"""
        )

    # ------------------------------------------------------------------
    # Whirlwind operators
    # ------------------------------------------------------------------

    @cmd2.with_category("Whirlwind operators")
    def do_discover(self, statement: cmd2.Statement) -> None:
        """Discover mosaics or metadata."""
        self._dispatch("discover", statement)

    def help_discover(self) -> None:
        self.poutput(
            """
usage:
  discover <subcommand> [options]

subcommands:
  mosaics
  metadata, meta

examples:
  discover mosaics
  discover metadata
"""
        )

    @cmd2.with_category("Whirlwind operators")
    def do_mosaic(self, statement: cmd2.Statement) -> None:
        """Run mosaic operators."""
        self._dispatch("mosaic", statement)

    def help_mosaic(self) -> None:
        self.poutput(
            """
usage:
  mosaic <subcommand> [options]

subcommands:
  downsample, ds
  tile, tesselate, t

examples:
  mosaic downsample
  mosaic downsample --mosaic=M-240119-DSM-a31f
  mosaic tile
"""
        )

    @cmd2.with_category("Whirlwind operators")
    def do_tiles(self, statement: cmd2.Statement) -> None:
        """Run tile operators."""
        self._dispatch("tiles", statement)

    def help_tiles(self) -> None:
        self.poutput(
            """
usage:
  tiles <subcommand> [options]

subcommands:
  export, e
  stitch, s

examples:
  tiles export
  tiles stitch
"""
        )

    @cmd2.with_category("Whirlwind operators")
    def do_stage(self, statement: cmd2.Statement) -> None:
        """Stage tile plans or damage paths."""
        self._dispatch("stage", statement)

    def help_stage(self) -> None:
        self.poutput(
            """
usage:
  stage <subcommand> [options]

subcommands:
  tiles, tiling, t
  paths, p

examples:
  stage tiles
  stage paths
"""
        )

    @cmd2.with_category("Whirlwind operators")
    def do_metamosaic(self, statement: cmd2.Statement) -> None:
        """Run metamosaic operators."""
        self._dispatch("metamosaic", statement)

    def help_metamosaic(self) -> None:
        self.poutput(
            """
usage:
  metamosaic <subcommand> [options]

subcommands:
  build, b

examples:
  metamosaic build
  metamosaic build --stem=denver
"""
        )

    @cmd2.with_category("Whirlwind operators")
    def do_mm(self, statement: cmd2.Statement) -> None:
        """Alias for metamosaic."""
        self._dispatch("mm", statement)

    def help_mm(self) -> None:
        self.help_metamosaic()

    @cmd2.with_category("Whirlwind operators")
    def do_database(self, statement: cmd2.Statement) -> None:
        """Run database operators."""
        self._dispatch("database", statement)

    def help_database(self) -> None:
        self.poutput(
            """
usage:
  database <subcommand> [options]

subcommands:
  init

examples:
  database init
"""
        )

    # ------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------

    @cmd2.with_category("Shell")
    def do_quit(self, _: cmd2.Statement) -> bool:
        """Quit the shell."""
        self.exit_code = 13
        return True

    @cmd2.with_category("Shell")
    def do_q(self, statement: cmd2.Statement) -> bool:
        """Alias for quit."""
        return self.do_quit(statement)

    @cmd2.with_category("Shell")
    def do_restart(self, _: cmd2.Statement) -> bool:
        """Restart the WHIRLWIND shell process."""
        os.execvp("W", ["W"])
        return True

    @cmd2.with_category("Shell")
    def do_r(self, statement: cmd2.Statement) -> bool:
        """Alias for restart."""
        return self.do_restart(statement)
