import os
import sqlite3
import sys

import arguments
import errors
import blessed

import log
from url_handler import get_file_url
import requests.exceptions
import urllib3.exceptions

args = arguments.parse_args()

logger = log.Logger(args.log_level)

LINE = "━"

# the platforms that there aren't tvp builds for
CLI_VIDEO_NO_SUPPORT = [
    'win32',
    'darwin',
    'cygwin'
]

# only a linux build for now
TVP_FILE_LINUX = "https://github.com/TheRealOrange/terminalvideoplayer/blob/main/tvp?raw=true"

TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})


# based off of https://github.com/acifani/boxing/blob/master/boxing/boxes.json
boxes = {
    "single": {
        "topLeft": "┌",
        "topRight": "┐",
        "bottomRight": "┘",
        "bottomLeft": "└",
        "vertical": "│",
        "horizontal": "─",
        "verticalRight": "┤",
        "verticalLeft": "├"
    },
    "double": {
        "topLeft": "╔",
        "topRight": "╗",
        "bottomRight": "╝",
        "bottomLeft": "╚",
        "vertical": "║",
        "horizontal": "═",
        "verticalRight": "╣",
        "verticalLeft": "╠"
    }
}
NL = '\n'
WS = ' '

term = blessed.Terminal()

HALF = '\N{LOWER HALF BLOCK}'

USERAGENT = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0"}

# set a constant for the platform
PLATFORM = sys.platform

# get the application data directory (operating system independent)
if PLATFORM == 'linux':
    DATA_DIR = os.path.expanduser('~/.local/share/reddit-dl/')
elif PLATFORM == 'win32':
    DATA_DIR = os.path.expanduser('~/AppData/Local/reddit-dl/')
elif PLATFORM == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/reddit-dl/')
else:
    # we only support linux, windows, and macOS for now
    raise errors.UnsupportedPlatformError("Unsupported platform: {}".format(PLATFORM))
logger.debug("Data directory: {}".format(DATA_DIR))


if not os.path.exists(DATA_DIR + 'ffplay'):
    logger.debug("ffplay not found, downloading")
    # these are the anonfile IDs
    try:
        if PLATFORM == 'win32':
            FFPLAY_FILE_WIN = get_file_url("56t6Q5V6x8")
        elif PLATFORM == 'darwin':
            FFPLAY_FILE_LINUX = get_file_url("Tcb0Q3Vbxb")
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError):
        # the user is offline
        pass

logger.debug("Connecting to database")
db = sqlite3.connect(DATA_DIR + "data.db")
logger.debug("Database connection established")
cur = db.cursor()
