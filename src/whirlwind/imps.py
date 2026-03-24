from __future__ import annotations

# =========================
# standard library
# =========================
import argparse
import csv
import hashlib
import heapq
import io
import json
import math
import os
import re
import shlex
import sys
import tarfile
import time
import uuid

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

# =========================
# third-party
# =========================
import numpy as np
import rasterio
import yaml

from osgeo import gdal, osr

from rasterio.windows import Window
from rasterio.warp import transform_bounds

# rich (UI / logging)
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    ProgressColumn,
    Task,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.traceback import install

# =========================
# explicit export surface
# =========================
__all__ = [
    # stdlib modules
    "argparse",
    "csv",
    "hashlib",
    "heapq",
    "io",
    "json",
    "math",
    "os",
    "re",
    "shlex",
    "sys",
    "tarfile",
    "time",
    "uuid",

    # stdlib objects
    "ABC",
    "abstractmethod",
    "contextmanager",
    "asdict",
    "dataclass",
    "field",
    "is_dataclass",
    "datetime",
    "timezone",
    "Path",
    "Any",
    "Dict",
    "Iterable",
    "Iterator",
    "List",
    "Mapping",
    "Optional",
    "Sequence",
    "Tuple",

    # third-party modules
    "np",
    "rasterio",
    "yaml",
    "gdal",
    "osr",

    # rasterio helpers
    "Window",
    "transform_bounds",

    # rich
    "Align",
    "Console",
    "Panel",
    "Progress",
    "ProgressColumn",
    "Task",
    "TextColumn",
    "TimeElapsedColumn",
    "Rule",
    "Table",
    "Text",
    "install",
]
