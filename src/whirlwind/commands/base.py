"""
    Command(ABC) class forms base interface for all w: commands.
"""


from abc import ABC, abstractmethod


# command class


class Command(ABC):
    """base interface for all commands"""
    name: str

    @abstractmethod
    def run(self, tokens: list[str], config: dict[str,Any]) -> int:
        raise NotImplementedError
    
    def help(self) -> dict[str,str]:
        raise NotImplementedError


