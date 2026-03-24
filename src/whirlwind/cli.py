
from whirlwind.imps import *
from .core.app import _build
from .utils import configurator as confio
from .utils.logger import Logger
from .ui.tui import TUI
from .core.shell import WShell

# for traceback
install(show_locals=True)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( "--config", type=str, default="config.yaml",
        help="path to yaml config, default config.yaml",)
    return parser

def main(argv: list[str] | None = None) -> int:
    ui = TUI()
    config = confio.load_(build_parser().parse_args(argv).config)
    ui.success(f"configuration loaded successfuly")
    lp = config.get("global").get("log")
    log = Logger(lp)
    app = _build(log)  
    shell = WShell(app,config,log) 
    return shell._run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
