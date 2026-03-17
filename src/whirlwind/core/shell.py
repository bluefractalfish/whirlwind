# handle token exceptions, 
# handle formatting 
# handle config loading 
# handle key normalization 
# hold ShellState 
from ..ui.tui import TUI 
import shlex 


class WShell:

    def __init__(self,app_instance, config, log):
       self.running = True
       self.app = app_instance
       self.config = config
       self.log = log 
       self.ui = TUI() 


    def _run(self) -> int:
        while self.running:
            try:
                ln = input("w: ").strip()
                self.ui.div(ln) 
            except EOFError:
                self.ui.error("error occured with input")
            except KeyboardInterrupt:
                self.ui.error("keboard interruption")
                continue 
            if not ln:
                continue 
            if ln in {"quit","exit","q"}:
                self.ui.success("quitting...")
                return 2
            if ln in {"help","h"}:
                self.ui.print("available commands:...")
                continue 
            try:
                tokens = shlex.split(ln) 
                self.app.run(tokens, self.config)
            except Exception as exc:
                self.ui.error(f"{exc}")
        return 0


