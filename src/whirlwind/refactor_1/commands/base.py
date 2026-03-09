"""
    Command(ABC) class forms base interface for all w: commands.
"""


import argparse
from abc import ABC, abstractmethod


# command class
class Command(ABC):
    """base interface for all commands"""
    name: str

    @abstractmethod
    def configure(self, subparser:argparse._SubParsersAction) -> None:
        """register command's subparser(s)"""
        raise NotImplementedError

    @abstractmethod
    def run(self, args:argparse.Namespace) -> int:
        """execute command and return exit code"""
        #force implementation for every command
        raise NotImplementedError

