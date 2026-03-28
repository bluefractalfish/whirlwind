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

from whirlwind.commands.base import Command
from rich.traceback import install 
import shlex 

install(show_locals=True)

class WShell:
    def __init__(self, app, config): 
        self.app = app 
        self.config = config 
        self.log = app.log.child("shell")
        self.cshells = {"quit"} 

    def run(self) -> int:
        while True:
            line = input("W: ").strip()
            try:
                if not line:
                    continue 
                if line in self.cshells: 
                    # handle shell commands 
                    print(line)
                    continue 
            except EOFError:
                print("ERROR")
                return_code = 11
            except KeyboardInterrupt:
                return 13 
            try:
                tokens = shlex.split(line)
                # HANDLE UNRECOGNIZED COMMAND 
                # RUN COMMAND
                # 0 -> success 
                # 1 -> unnamed error 

                ret = self.app.run(tokens, self.config)
                continue
            except KeyboardInterrupt:
                return 0 
            except Exception as exc:
                raise exc 
                continue 
        return 0 
            
