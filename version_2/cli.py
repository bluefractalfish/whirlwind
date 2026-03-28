
from whirlwind.imps import *
from .core.app import _build
from .utils import configurator as confio
from .utils.logger import Logger
from .ui.tui import PANT
from .core.shell import WShell
from .utils.timer import *
from .core.state import STATE 

# for traceback
install(show_locals=True)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( "--config", type=str, default="config.yaml",
        help="path to yaml config, default config.yaml",)
    return parser

def main(argv: list[str] | None = None) -> int:
    config = confio.load_(build_parser().parse_args(argv).config)
    STATE.config = config
    PANT.success(f"configuration loaded successfuly")
    lp = config.get("global").get("log")
    log = Logger(lp)
    app = _build(log)  
    shell = WShell(app,config,log) 

    return shell._run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
