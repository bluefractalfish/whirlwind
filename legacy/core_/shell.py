""" whirlwind.core.shell 

    PURPOSE: 
        - interactive REPL for running Whirlwind Commands 
        - this module *IS* the user facing UI. all other packages remain UI free 
    BEHAVIOR: 
        - read line, tokenize with shlex, dispatch to WhirlwindApp 
        - maintain STATE toggles 
    PUBLIC:
        WShell

"""

from whirlwind.commands.test import RestartShell, QuitShell
from whirlwind.commands.base import Command
from rich.traceback import install 
import shlex 

#install(show_locals=True)

class WShell:
    def __init__(self, app): 
        self.app = app 
        self.running = 0
        self.cshells = {
                "restart": RestartShell(),
                "r": RestartShell(),
                "quit": QuitShell(),
                "q" : QuitShell()}

        # set out directory for this instance 
        #my_out_dir = self.config.parse("global","out") + "/run-"+ self.app.run_id
    def run(self) -> int:
        while self.running == 0:
            line = input("> ").strip()
            try:
                if not line:
                    continue 
            except EOFError:
                print("ERROR")
            except KeyboardInterrupt:
                self.running = 13 
                pass
            try:
                tokens = shlex.split(line)
                # HANDLE UNRECOGNIZED COMMAND 
                # RUN COMMAND
                # 0 -> success 
                # 1 -> unnamed error 
                head = tokens[0]
                if head in self.cshells:
                    self.running = self.cshells[head].run(tokens[1:])
                    continue
                ret_code = self.app.run(tokens)
                match ret_code:
                    case 11:
                        print("unrecognized command")
                    case 13:
                        self.running = ret_code
                continue
            except KeyboardInterrupt:
                self.running = 13 
                pass
            except Exception as exc:
                raise exc 

        return_code = self.running
        return return_code 
            
