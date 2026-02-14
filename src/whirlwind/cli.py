
from typing import List, Optional

from . import toolbox

def main(argv: Optional[List[str]] = None) -> int:
    return toolbox.run(argv)

if __name__ == "__main__":
    raise SystemExit(main())

