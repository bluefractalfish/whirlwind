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
