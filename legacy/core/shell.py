# handle token exceptions, 
# handle formatting 
# handle config loading 
# handle key normalization 
# hold ShellState 
from whirlwind.imps import *
from ..ui.tui import PANT
from ..utils.configurator import get_version
from .state import STATE 


class WShell:

    
    def __init__(self,app_instance, config, log):
       self.version = config.get("global").get("version")
       self.running = 0
       self.app = app_instance
       self.config = config
       self.log = log 
       PANT.c_box(f"W:HIRLWIND-{self.version}--INITIALIZING WSHELL--RUN_ID: {self.app.run_id}",l="QUIET")


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
                    
                if ln in {"verbose","v"}:
                    print(f"old:{STATE.VERBOSE}")
                    STATE.VERBOSE = not STATE.VERBOSE 
                    PANT.change_volume()
                    print(f"new:{STATE.VERBOSE}")
                    continue
                if ln in {"timed","t"}:
                    print(STATE.TIME)
                    STATE.TIME = not STATE.TIME
                    print(STATE.TIME)
                    continue

            except EOFError:
                PANT.error(f"error occured with input: {ln}")
            except KeyboardInterrupt:
                PANT.error("keboard interruption")
                PANT.error("forced quit")
                return 0 
            try:
                tokens = shlex.split(ln) 
                ret = self.app.run(tokens, self.config)
                if ret == 3:
                    PANT.error(f"unrecognized command: {ln}")
            except KeyboardInterrupt:
                PANT.success(f"quitting with keyboard interruption",l="VERBOSE")
                self.running = 1
                return 0
            except Exception as exc:
                PANT.error(f"{exc}")
                continue
        return 0

    def _restart(self):
        """replace current process with new instance of whirlwind.cli"""
        PANT.success("RESTARTING","QUIET")
        PANT.success(l="QUIET")
        os.execvp("W", ["W"])

    def _handle_quit(self):
        confirm = input("are you sure you want to quit? (y or n) ")
        if confirm in {"y","Y"}:
            PANT.success("QUITTING","QUIET")
            return 2
        else:
            return 0

    def _be_helpful(self):
        ch = [] 
        for c in self.app._help():
            for r in  c.items(): 
                ch.append(r) 
        PANT.table("", ["command", "command specification"],ch)
        
