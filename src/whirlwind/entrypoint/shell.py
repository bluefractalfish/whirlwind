from __future__ import annotations

import os
import shlex

import cmd2

from whirlwind.entrypoint.app import WhirlwindApp


class WShell(cmd2.Cmd):

    def __init__(self, app: WhirlwindApp) -> None:
        super().__init__(
            allow_cli_args=False,
            persistent_history_file=".whirlwind_history",
        )
        self.app = app
        self.exit_code = 0
        run_id = getattr(app, "run_id", "dev")
        self.intro = (
                "WHIRLWIND SHELL \n"
                "type help or ? for list of commands \n"
                f"run_id: {run_id}"
                )
        self.prompt = f"> "
        # Keep cmd2 from treating unknown input as OS shell commands.
        self.default_to_shell = False

    def run(self) -> int:
        self.cmdloop()
        return self.exit_code

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

        try:
            ret_code = self.app.run(tokens)
        except Exception:
            raise

        self.exit_code = ret_code

        match ret_code:
            case 0:
                return
            case 3:
                self.perror("usage error")
            case 11:
                self.perror("unrecognized command")
            case 13:
                self.exit_code = 13
                self._should_quit = True
            case _:
                self.perror(f"command failed with code {ret_code}")

    def do_quit(self, _: cmd2.Statement) -> bool:
        """Quit the shell."""
        self.exit_code = 13
        return True

    def do_q(self, statement: cmd2.Statement) -> bool:
        """Alias for quit."""
        return self.do_quit(statement)

    def do_restart(self, _: cmd2.Statement) -> bool:
        """Restart the WHIRLWIND shell process."""
        os.execvp("W", ["W"])
        return True

    def do_r(self, statement: cmd2.Statement) -> bool:
        """Alias for restart."""
        return self.do_restart(statement)
