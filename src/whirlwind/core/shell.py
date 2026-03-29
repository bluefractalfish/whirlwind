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

from whirlwind.commands.cshell import RestartShell 
from whirlwind.commands.cshell import QuitShell 
from whirlwind.commands.cshell import List
from whirlwind.commands.base import Command
from rich.traceback import install 
import shlex 

install(show_locals=True)

class WShell:
    def __init__(self, app, config): 
        self.app = app 
        self.config = config 
        self.running = 0
        self.log = app.log.child("shell")
        self.cshells = {
                "ls": List(),
                "list": List(),
                "restart": RestartShell(),
                "r": RestartShell(),
                "quit": QuitShell(),
                "q" : QuitShell()}

    def run(self) -> int:
        while self.running == 0:
            line = input("W: ").strip()
            try:
                if not line:
                    continue 
            except EOFError:
                print("ERROR")
            except KeyboardInterrupt:
                self.running = 13 
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
                ret_code = self.app.run(tokens, self.config)
                match ret_code:
                    case 11:
                        print("unrecognized command")
                    case 13:
                        self.running = ret_code
                continue
            except KeyboardInterrupt:
                self.running = 13 
            except Exception as exc:
                raise exc 

        return_code = self.running
        return return_code 
            
