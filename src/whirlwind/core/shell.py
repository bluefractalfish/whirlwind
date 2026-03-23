# handle token exceptions, 
# handle formatting 
# handle config loading 
# handle key normalization 
# hold ShellState 
from ..ui.tui import TUI 
from ..utils.configure import get_version
import shlex 
import os



class WShell:

    
    def __init__(self,app_instance, config, log):
       self.version = config.get("global").get("version")
       self.running = 0
       self.app = app_instance
       self.config = config
       self.log = log 
       self.ui = TUI() 
       self.ui.c_box(f"W:HIRLWIND-{self.version}--INITIALIZING WSHELL--RUN_ID: {self.app.run_id}",l="TOP")


    def _run(self) -> int:
        while self.running == 0:
            ln = input("w: ").strip()
            try:
                if not ln:
                    continue 
                if ln in {"quit","exit","q"}:
                    self.running = self._handle_quit()
                    continue
                if ln in {"help","h"}:
                    self._be_helpful()
                    continue 
                if ln in {"restart","r"}:
                    self._restart()

            except EOFError:
                self.ui.error(f"error occured with input: {ln}")
            except KeyboardInterrupt:
                self.ui.error("keboard interruption")
                self.ui.error("forced quit")
                return 0 
            try:
                tokens = shlex.split(ln) 
                ret = self.app.run(tokens, self.config)
                if ret == 3:
                    self.ui.error(f"unrecognized command: {ln}")
            except KeyboardInterrupt:
                self.ui.success(f"quitting with keyboard interruption",l="INFO")
                self.running = 1
                return 0
            except Exception as exc:
                self.ui.error(f"{exc}")
                continue
        return 0

    def _restart(self):
        """replace current process with new instance of whirlwind.cli"""
        self.ui.success("RESTARTING","TOP")
        self.ui.success(l="TOP")
        os.execvp("W", ["W"])

    def _handle_quit(self):
        confirm = input("are you sure you want to quit? (y or n) ")
        if confirm in {"y","Y"}:
            self.ui.success("QUITTING","TOP")
            return 2
        else:
            return 0

    def _be_helpful(self):
        ch = [] 
        for c in self.app._help():
            for r in  c.items(): 
                ch.append(r) 
        self.ui.table("", ["command", "command specification"],ch)
        
