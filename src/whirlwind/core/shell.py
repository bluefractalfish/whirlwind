# handle token exceptions, 
# handle formatting 
# handle config loading 
# handle key normalization 
# hold ShellState 
from ..ui.tui import TUI 
import shlex 


class WShell:

    def __init__(self,app_instance, config, log):
       self.running = 0
       self.app = app_instance
       self.config = config
       self.log = log 
       self.ui = TUI() 
       self.ui.c_box("INITIALIZING WSHELL V=A.0",l="INFO")


    def _run(self) -> int:
        while self.running == 0:
            try:
                ln = input("w: ").strip()

                if not ln:
                    continue 
                if ln in {"quit","exit","q"}:
                    self.running = self._handle_quit()
                    continue
                if ln in {"help","h"}:
                    self._be_helpful()
                    continue 

            except EOFError:
                self.ui.error("error occured with input")
            except KeyboardInterrupt:
                self.ui.error("keboard interruption")
                return 0 
            try:
                tokens = shlex.split(ln) 
                ret = self.app.run(tokens, self.config)
                if ret == 3:
                    self.ui.error("unrecognized command")
            except KeyboardInterrupt:
                self.ui.success(f"quitting with keyboard interruption",l="INFO")
                self.running = 1
                return 0
            except Exception as exc:
                self.ui.error(f"{exc}")
                continue
        return 0

    def _handle_quit(self):
        confirm = input("are you sure you want to quit? (y or n) ")
        if confirm in {"y","Y"}:
            self.ui.success("quitting whirlwind",l="INFO")
            return 2
        else:
            return 0

    def _be_helpful(self):
        title = ["commands", "spec"]
        
        self.app._help()

