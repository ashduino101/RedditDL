# Written by Ashton Fairchild (ashduino101) starting on 2022-04-08
# License: MIT
#
# This program is intended as a command-line application to allow downloading and browsing of Reddit content,
# such as subreddits, posts, and comments.
#

# built-in
import re
import subprocess
import time
from itertools import chain
import sys
import sqlite3
from os.path import exists
import os
import datetime
import hashlib
import argparse
import webbrowser
import stat
from inspect import signature
import shutil
from types import SimpleNamespace

# 3rd-party
import cv2
import moviepy.editor
import pygame
import requests
import termcolor as tc
import blessed
from PIL import Image
from pick import pick


# Constants to make things easier
class Constants(SimpleNamespace):
    LINE = "━"


# Some utility functions
class Utils(SimpleNamespace):
    @staticmethod
    def progress_bar(percent, width=50, color="green", bg="gray"):
        # the formatting isn't great, but it works
        return tc.colored(
            Constants.LINE, color
        ) * int(percent * width // 100) + tc.colored(
            Constants.LINE, bg
        ) * (width - int(percent * width // 100)) + " " + str(percent) + "%"

    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')


# we create a custom logger class for fancy formatting since I'm too lazy to use logging
class Logger:
    def __init__(self, level):
        if level.lower() not in self.levels:
            raise ValueError(f"Invalid log level: {level}")
        self.level = self.levels[level.lower()]
        self.level_name = level

    # the logging levels
    levels = {
        'debug': 0,
        'info': 1,
        'warning': 2,
        'error': 3,
    }

    @staticmethod
    def log(msg: str, level: str, color: str) -> str:
        return tc.colored(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{level}] - {msg}", color)

    def debug(self, msg: str):
        if self.level <= self.levels['debug']:
            print(self.log(msg, 'DEBUG', 'cyan'))

    def info(self, msg: str):
        if self.level <= self.levels['info']:
            print(self.log(msg, 'INFO', 'white'))

    def warn(self, msg: str):
        if self.level <= self.levels['warning']:
            print(self.log(msg, 'WARNING', 'yellow'))

    def error(self, msg: str):
        if self.level <= self.levels['error']:
            print(self.log(msg, 'ERROR', 'red'))


# Exceptions
class UnsupportedPlatformError(Exception):
    def __init__(self, platform, message="Your platform '{}' is not supported, sorry!"):
        self.platform = platform
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message.format(self.platform)


parser = argparse.ArgumentParser(description="Downloads media from a subreddit")
parser.description = "Downloads a given number of posts from a subreddit for offline viewing."

# arguments for the command line
parser.add_argument(
    "-m",
    "--mode",
    help="Mode to run in",
    choices=["download", "list"],
    default="list"
)

parser.add_argument(
    "--sub",
    "-s",
    help="The subreddit to download or view from (no leading /r/)",
    type=str,
    default="all"
)

parser.add_argument(
    "-l",
    "--limit",
    type=int,
    default=50,
    help="The amount of posts to download"
)

parser.add_argument(
    "-L",
    "--log-level",
    type=str,
    default="ERROR",
    help="The log level to use"
)

parser.add_argument(
    "-p",
    "--use-purepython-media",
    action="store_true",
    help="Use pure python video if CLI video is used (very slow, but works on all platforms)",
    default=False
)

parser.add_argument(
    "-c",
    "--cli-media",
    action="store_true",
    help="Display media to the console using text",
    default=False
)

parser.add_argument(
    "--order-by-score",
    action="store_true",
    help="Order by score instead of ID",
    default=False
)

parser.add_argument(
    "--only-nsfw",
    action="store_true",
    help="Only show or download NSFW posts",
    default=False
)

parser.add_argument(
    "-w",
    "--no-warn-nsfw",
    action="store_true",
    help="Don't warn about NSFW posts",
    default=False
)

parser.add_argument(
    "--no-nsfw",
    action="store_true",
    help="Don't show or download NSFW posts",
    default=False
)

parser.add_argument(
    "--only-videos",
    action="store_true",
    help="Only show or download videos",
    default=False
)

parser.add_argument(
    "--list-subreddits",
    action="store_true",
    help="List all downloaded subreddits.",
    default=False
)

parser.add_argument(
    "--interactive",
    "-i",
    action="store_true",
    help="Starts an interactive console",
    default=False
)

parser.add_argument(
    "--reset",
    action="store_true",
    help="Reset the database and filesystem",
)

args = parser.parse_args()

logger = Logger(args.log_level)

# the platforms that there aren't tvp builds for
CLI_VIDEO_NO_SUPPORT = [
    'win32',
    'darwin',
    'cygwin'
]

# only a linux build for now
TVP_FILE_LINUX = "https://github.com/TheRealOrange/terminalvideoplayer/blob/main/tvp?raw=true"

text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})


def is_text(_bytes):
    return not bool(_bytes.translate(None, text_chars))


# this is just for the setup process (using anonfile as a hosting service for the ffplay builds)
def get_file_url(file_id: str) -> str:
    return "".join(
        re.findall(
            r"(https://cdn-\d*.anonfiles.com/)(\w{10})(/[\w-]{19}/)(.*)\"",
            requests.get("https://www.anonfiles.com/" + file_id).text
        )[0]
    )


# these are the anonfile IDs
FFPLAY_FILE_WIN = get_file_url("56t6Q5V6x8")
FFPLAY_FILE_LINUX = get_file_url("Tcb0Q3Vbxb")

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
    raise UnsupportedPlatformError("Unsupported platform: {}".format(PLATFORM))

# create the data directory if it doesn't exist
if not exists(DATA_DIR):
    logger.debug("Creating data directory")
    os.mkdir(DATA_DIR)

# create the directory for all the files if it doesn't exist (files are stored in the filesystem for performance)
if not exists(DATA_DIR + "media"):
    logger.debug("Creating media directory")
    os.mkdir(DATA_DIR + "media")

# download terminal video player if it hasn't been downloaded yet
if not exists(DATA_DIR + "tvp"):
    logger.debug("Downloading tvp")
    with open(DATA_DIR + "tvp", "wb") as f:
        f.write(requests.get(TVP_FILE_LINUX).content)
        st = os.stat(DATA_DIR + "tvp")
        # chmod the file so that it can be executed (doesn't do it by default)
        os.chmod(DATA_DIR + "tvp", st.st_mode | stat.S_IEXEC)

# download ffplay for linux or windows if it hasn't been downloaded yet
if not (exists(DATA_DIR + "ffplay") or exists(DATA_DIR + "ffplay.exe")):
    if PLATFORM == 'linux':
        logger.debug("Downloading ffplay")
        with open(DATA_DIR + "ffplay", "wb") as f:
            # linux
            resp = requests.get(FFPLAY_FILE_LINUX)
            if resp.status_code == 200:
                f.write(resp.content)
                st = os.stat(DATA_DIR + "ffplay")
                # for some reason, the file isn't executable by default, though it should be
                os.chmod(DATA_DIR + "ffplay", st.st_mode | stat.S_IEXEC)
            else:
                logger.error("Failed to download ffplay. Non-CLI video playback will not function.")

    elif PLATFORM == 'win32':
        logger.debug("Downloading ffplay")
        with open(DATA_DIR + "ffplay.exe", "wb") as f:
            # windows
            resp = requests.get(FFPLAY_FILE_WIN)
            if resp.status_code == 200:
                # make sure the download worked, in case anonfile is down or something
                f.write(resp.content)
            else:
                logger.error("Failed to download ffplay. Video playback will not function.")

db = sqlite3.connect(DATA_DIR + "data.db")
logger.debug("Connected to database")
cur = db.cursor()

USERAGENT = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0"}


class Handlers(SimpleNamespace):
    @staticmethod
    def imgur(url):
        return re.findall(r"https://i\.imgur\.com/\w+\.(png|jpeg|gif|gifv|jpg)", url)[0]


def get_media_url(post: dict) -> str or None:
    if "//imgur.com" in post["url"]:
        # return Handlers.imgur(post["url"])
        return None
    if post["is_video"]:
        url = post["media"]["reddit_video"]["fallback_url"]
    else:
        url = post["url"] if not post["url"].startswith("/r/") else None  # selftext posts

    if url is None:
        return None

    # check if url is a cross-post
    if url.startswith("https://www.reddit.com/r/"):
        if url.endswith("/"):
            return None
        # get the post
        print(url)
        data = requests.get(url + ".json", headers=USERAGENT).json()
        # get the media url
        url = get_media_url(data[0]["data"]["children"][0]["data"])

    return url


def generate_hash(post_id: str) -> str:
    return hashlib.md5(post_id.encode()).hexdigest()


def download(subreddit: str, limit: int = 50) -> int:

    # sometimes, the limit can be passed as a string, not sure why
    limit = int(limit)

    # check if the sub exists
    if not requests.get(f"https://reddit.com/r/{subreddit}.json",
                        headers=USERAGENT).url == f"https://www.reddit.com/r/{subreddit}.json":
        raise ValueError(f"Subreddit '{subreddit}' does not exist!")

    # we'll use a table per subreddit
    # (but a single table could also work, if we just select where the subreddit column is the wanted subreddit)

    # ensure the table exists before we start
    # we don't need to sanitize the subreddit, since it can't contain malicious queries
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS "%s" (
            "id"	TEXT UNIQUE,
            "title"	TEXT,
            "link"	TEXT,
            "generated_md5"	TEXT,
            "author"	TEXT,
            "time"	INT,
            "type"	TEXT,
            "file_url"	TEXT,
            "is_video"	INT,
            "nsfw"	INT,
            "spoiler"	INT,
            "score"	INT,
            "vote_ratio"	INT,
            "subreddit"	TEXT,
            "path"	TEXT
        );
        """ % subreddit.lower()
    )

    db.commit()

    posts = []

    # we'll use the reddit json api to get the posts
    # first request to get the last id
    data = requests.get(f"https://www.reddit.com/r/{subreddit}.json?count=25", headers=USERAGENT).json()
    for i in range(0, (limit // 25)):
        last_id = ""
        for post in data["data"]["children"]:
            del post["data"]["all_awardings"]  # we don't need this, and it's a lot of data
            if args.only_nsfw and not post["data"]["over_18"]:
                continue
            elif args.no_nsfw and post["data"]["over_18"]:
                continue
            posts.append(post["data"])
            last_id = post["data"]["name"]

        data = requests.get(
            f"https://www.reddit.com/r/{subreddit}.json?count=25&after={last_id}",
            headers=USERAGENT
        ).json()

    logger.info(
        f"{len(posts)} posts found ({len(posts) - limit} {'extra' if (len(posts) - limit) > 0 else 'discarded'} posts)")

    # create the media directory for the sub if it doesn't exist
    if not exists(DATA_DIR + f"media/{subreddit}/"):
        logger.info(f"Creating media directory for {subreddit}")
        os.mkdir(DATA_DIR + f"media/{subreddit}/")

    # insert the data into the database
    for post in posts:
        file = get_media_url(post)
        if file is None:
            logger.info(f"Self-text or invalid post {post['title']} (no file)")
            continue
        try:
            cur.execute(
                'INSERT INTO "%s" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)' % subreddit,
                (
                    post["id"],
                    post["title"],
                    post["permalink"],
                    generate_hash(get_media_url(post)) if get_media_url(post) else None,
                    post["author"],
                    int(post["created_utc"]),
                    "mp4" if post["is_video"] else "jpg",
                    get_media_url(post), post["is_video"],
                    post["over_18"],
                    post["spoiler"],
                    post["score"],
                    post["upvote_ratio"] * 100,
                    subreddit,
                    (DATA_DIR +
                     f"media/{subreddit}/{generate_hash(get_media_url(post))}")
                    if get_media_url(post)
                    else None
                )
            )
        except sqlite3.IntegrityError:
            logger.debug(f"Post {post['id']} already exists in database")
            continue

    db.commit()
    logger.info("Inserted post data into database")

    # Download the files
    for i, post in enumerate(posts):
        file = get_media_url(post)
        if file is None:
            logger.info(f"Self-text post {post['title']} (no file)")
            continue
        file_hash = generate_hash(file)
        name = DATA_DIR + f"media/{subreddit}/{file_hash}"
        with open(name, "wb") as media:
            media.write(requests.get(file, headers=USERAGENT).content)

        logger.info(f"Downloaded post {post['name']} to {name} ({i + 1}/{len(posts)})")

    return len(posts)


class Post:
    def __init__(
            self,
            post_id,
            title,
            link,
            generated_md5,
            author,
            created_at,
            file_type,
            file_url,
            is_video,
            nsfw,
            spoiler,
            score,
            vote_ratio,
            subreddit,
            path
    ):
        self.id = post_id
        self.title = title
        self.link = link
        self.generated_md5 = generated_md5
        self.author = author
        self.time = created_at
        self.type = file_type
        self.file_url = file_url
        self.is_video = is_video
        self.nsfw = nsfw
        self.spoiler = spoiler
        self.score = score
        self.vote_ratio = vote_ratio
        self.subreddit = subreddit
        self.path = path


term = blessed.Terminal()

HALF = '\N{LOWER HALF BLOCK}'


def image(im):
    im.thumbnail((term.width, term.height * 2))
    im.convert("RGB")
    pixels = im.load()
    res = ''
    for y in range(im.size[1] // 2):
        res += " " * ((term.width - im.size[0]) // 2)
        for x in range(im.size[0]):
            # false positives, pycharm doesn't like this for some reason

            # we can't unpack because sometimes there aren't 3 values, not sure why
            # noinspection PyUnresolvedReferences
            p = pixels[x, y * 2]
            r = p[0]
            g = p[1]
            b = p[2]

            # noinspection PyUnresolvedReferences
            p2 = pixels[x, y * 2 + 1]
            r2 = p2[0]
            g2 = p2[1]
            b2 = p2[2]

            res += term.on_color_rgb(r, g, b) + term.color_rgb(r2, g2, b2) + HALF
        res += term.normal + (" " * ((term.width - im.size[0]) // 2)) + '\n'
    return res


def video(path):
    with term.cbreak(), term.hidden_cursor(), term.fullscreen():
        # get start time
        start_time = time.time()
        # variables
        frame_count = 1
        dropped_frames = 0
        # load video
        capture = cv2.VideoCapture(path)
        # get fps
        fps = capture.get(cv2.CAP_PROP_FPS)
        # load audio from video
        v = moviepy.editor.VideoFileClip(path)
        audio = v.audio
        if audio:
            audio.write_audiofile(path.split(".")[0] + ".wav")
            # play audio
            pygame.mixer.init()
            pygame.mixer.music.load(path.split(".")[0] + ".wav")
        pause = False
        first = True
        # main loop
        while capture.isOpened():
            # for pause/exit
            inp = term.inkey(timeout=0.01)
            # esc
            if inp == "\x1b" or inp == "q":
                break
            if inp == ' ':
                pause = not pause
                if audio:
                    pygame.mixer.music.pause() if pause else pygame.mixer.music.unpause()
                print(term.home + term.move_y((term.height - 1) // 2))
                print(
                    term.black_on_white(
                        term.center(
                            'Paused. Press %s to unpause, or %s or %s to exit.' % (
                                term.italic(term.bold("Space")) + term.normal,
                                term.italic(term.bold("Escape")) + term.normal,
                                term.italic(term.bold("Q")) + term.normal
                            )
                        )
                    )
                )
            if not pause:
                if first:
                    if audio:
                        pygame.mixer.music.play()
                    first = False
                ret, frame = capture.read()
                elapsed = time.time() - start_time
                expected_frame = int(elapsed * fps)
                if frame_count < expected_frame:
                    frame_count += 1
                    dropped_frames += 1
                    continue
                if not ret:
                    break
                frame_count += 1
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(img)
                sys.stdout.write(term.home + image(im))
                sys.stdout.write(
                    term.white_on_black +
                    "Elapsed time: {} | "
                    "Actual frame: {} | "
                    "Theoretical frame: {} | "
                    "Dropped frames: {} | "
                    "FPS: {}".format(
                        elapsed,
                        frame_count - dropped_frames,
                        expected_frame,
                        dropped_frames,
                        (frame_count - dropped_frames) / elapsed
                    )
                )
                sys.stdout.flush()

    capture.release()
    cv2.destroyAllWindows()
    pygame.mixer.music.stop()


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


# modified from https://github.com/acifani/boxing/blob/master/boxing/boxing.py
def boxing(texts: list, style: str = 'single') -> str:
    chars = boxes.get(style, boxes['single'])
    longest = str(list(reversed(sorted(list(chain.from_iterable([t.splitlines() for t in texts])), key=len)))[0])

    def ansi_escape(t: str) -> str:
        regex = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        return regex.sub('', t)

    max_line_len = max(map(lambda l: len(ansi_escape(l)), longest.splitlines()))
    final = ""
    for i, text in enumerate(texts):
        lines = text.splitlines()
        horizontal_margin = WS * 3
        horizontal_padding = WS * 3
        horizontal_line = chars['horizontal'] * (max_line_len + 6)
        if i == 0:
            top_bar = horizontal_margin + \
                      chars['topLeft'] + horizontal_line + chars['topRight']
        else:
            top_bar = ""
        if i == len(texts) - 1:
            bottom_bar = horizontal_margin + \
                         chars['bottomLeft'] + horizontal_line + chars['bottomRight']
        else:
            bottom_bar = horizontal_margin + \
                         chars['verticalLeft'] + horizontal_line + chars['verticalRight']
        left = horizontal_margin + chars['vertical'] + horizontal_padding
        right = horizontal_padding + chars['vertical']
        vertical_padding = NL + left + WS * max_line_len + right
        top = top_bar + vertical_padding
        middle = ''
        for line in lines:
            fill = WS * (max_line_len - len(ansi_escape(line)))
            middle += NL + left + line + fill + right
        bottom = vertical_padding + NL + bottom_bar
        final += top + middle + bottom

    return final


def handle_media(post: Post):
    file = DATA_DIR + \
           f"media/{post.subreddit}/{post.generated_md5}"
    if not exists(file):
        r = input("This post is not in the filesystem. "
                  "Would you like to synchronize the filesystem with the database? [Y/n] ") or 'Y'
        if r.lower() == 'y':
            sync_files(post.subreddit)
        else:
            raise FileNotFoundError(f"{file} not in filesystem.")

    with open(file, 'rb') as o:
        one_kb = o.read(1024)
        if is_text(one_kb):
            print("Sorry, this post appears to be invalid! "
                  "Please report this on the repository along with the post's ID.")
            return
    if args.cli_media:
        if post.is_video or post.file_url.endswith('.gif'):
            if args.use_purepython_media:
                video(DATA_DIR + f"media/{post.subreddit}/{post.generated_md5}")
            else:
                if sys.platform in CLI_VIDEO_NO_SUPPORT:
                    raise NotImplementedError(
                        "Command line video playing on your platform is not yet supported, sorry! "
                        "You can instead use the pure python video player, "
                        "or don't use the CLI video argument, which will call ffplay on the file instead."
                    )
                else:
                    print("Using C++ terminal video player (Linux-only, but faster than pure python)")
                    subprocess.call([DATA_DIR + "tvp", file])
        else:
            with term.cbreak(), term.fullscreen(), term.hidden_cursor():
                print(
                    image(
                        Image.open(DATA_DIR + f"media/{post.subreddit}/{post.generated_md5}")
                    )
                )
                print(term.home + term.move_y(term.height // 2))
                print(term.white_on_black(term.center('Press any key to exit.')))
                start_time = time.time()
                while True:
                    key = term.inkey(timeout=0.1)
                    if key:
                        break
                    if time.time() - start_time > 1:
                        print(
                            term.clear + image(
                                Image.open(
                                    DATA_DIR + f"media/{post.subreddit}/{post.generated_md5}")
                            )
                        )
    else:
        subprocess.call([DATA_DIR + "ffplay", file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def header(width: int = term.width):
    row = (width - 10) // 5
    row -= 3
    header_text = "Title" + (" " * row) + "Author" + (" " * row) + "Subreddit" + (" " * row) + "Score" + "\n"
    header_text += ("=" * width)
    return header_text


def format_listing(post: Post, width: int = term.width):
    row = (width - 10) // 5
    title = ((post.title[:row] + '..') if len(post.title) > row else post.title) + " " * (
            row - (len(
                post.title.encode('utf-16-le')
                ) // 2)
    )  # to avoid unicode confusion
    author = post.author + " " * (row - len(post.author))
    subreddit = post.subreddit + " " * (row - len(post.subreddit))
    score = str(post.score) + " " * (row - len(str(post.score)))
    is_nsfw = "yes" if post.nsfw else "no" + " " * (row - len("yes" if post.nsfw else "no"))
    return f"{title} | {author} | {subreddit} | {score} | {is_nsfw}"


def list_posts(subreddit: str, limit: int = 50) -> list[Post]:
    # limit can be passed as a string for some reason
    limit = int(limit)
    # make sure the subreddit is lowercase before we check
    subreddit = subreddit.lower()
    cur.execute('SELECT `name` FROM `sqlite_master` WHERE `type`="table"')
    subreddits = [col[0] for col in cur.fetchall()]
    if subreddit not in subreddits:
        r = input(f"You have not downloaded any posts from {subreddit}. "
                  f"Would you like to download posts from it? [Y/n] ") or 'Y'
        if r.lower() == 'y':
            download(subreddit, limit)
        else:
            print("You have not downloaded any posts from this subreddit yet.")
            return []

    post_index = 0
    query = 'SELECT * FROM "%s"' % subreddit

    if args.only_nsfw:
        query += " WHERE nsfw = 1"

    # I still don't know how to format this properly, so I'm just going to do it with a lot of if statements
    if args.only_nsfw and args.only_videos:
        query += " AND is_video = 1"

    if args.only_videos and not args.only_nsfw:
        query += " WHERE is_video = 1"

    if args.order_by_score:
        query += " ORDER BY score DESC"

    query += " LIMIT %d" % limit

    logger.debug("Executing query: %s" % query)

    while True:
        cur.execute(query)
        posts = []
        for row in cur.fetchall():
            posts.append(Post(*row))
        if len(posts) == 0:
            inp = input("You have not downloaded any posts from this subreddit yet. Download them now? [Y/n]") or "y"
            if inp.lower() == "y":
                download(subreddit, limit)

        options = [format_listing(post) for post in posts]

        _, post_index = pick(options, header(), indicator='>', default_index=post_index)
        post = posts[post_index]

        if post.nsfw and args.no_warn_nsfw:
            print(
                term.center(
                    term.bold_yellow + "This post is marked as NSFW. "
                                       "To disable this warning, use the --no-warn-nsfw flag. "
                                       "Are you sure you want to view this post?" + term.normal
                )
            )

        print(term.clear + boxing(
            [
                post.title,

                f"Score: {post.score} | "
                f"Author: {post.author} | "
                f"Permalink: {post.link} | "
                f"Subreddit: {post.subreddit} | "
                f"NSFW: {'yes' if post.nsfw else 'no'}",

                "Press Q to exit\n" +
                ("Press V to view the image\n" if post.type == "jpg" else "Press V to play the video\n") +
                f"Press O to open the link\n"
            ],
            'double'))
        with term.cbreak():
            while True:
                c = term.inkey(timeout=0.1)
                if c == term.KEY_ESCAPE or c == 'q':
                    break
                elif c == 'v':
                    handle_media(post)
                elif c == 'o':
                    webbrowser.open("https://reddit.com" + post.link)


def sync_files(subreddit: str):
    if not os.path.exists(DATA_DIR + f"media/{subreddit}"):
        os.mkdir(DATA_DIR + f"media/{subreddit}")

    cur.execute('SELECT `file_url`, `path` FROM `%s`' % subreddit)
    for row in cur.fetchall():
        if not exists(row[1]):
            with open(row[1], 'wb') as file:
                file.write(requests.get(row[0]).content)
                logger.info("Downloaded %s to %s" % (row[0], row[1]))


class Command:
    def __init__(self, name, description, func):
        self.name = name
        self.description = description
        self.func = func


class CommandGroup:
    def __init__(self, name):
        self.name = name


class InteractiveConsole:
    def __init__(self, database):
        logger.level = 0
        self.db = database
        self.commands = {
            "Console": CommandGroup("Basic"),
            "help": Command("help", "Prints this help message", self.help),
            "exit": Command("exit", "Exits the interactive console", self.exit),
            "clear": Command("clear", "Clears the screen", self.clear),

            "Basic": CommandGroup("Reddit"),
            "download": Command("download", "Downloads posts from a subreddit", self.download),
            "list": Command("list", "Lists posts from a subreddit", self.list),
            "open": Command("open", "Opens a post in the browser", self.open),
            "delete": Command("delete", "Deletes a post from the database", self.delete),
            "sync": Command("sync", "Synchronizes the media files with the database", self.sync),
            "list_downloaded": Command("list_downloaded", "Lists downloaded subreddits", self.list_downloaded),

            "Dangerous": CommandGroup("Dangerous"),
            "reset": Command("reset", "Deletes the database and removes all media files from filesystem", self.reset),
        }

    def help(self):
        print("Available commands:")
        for command in self.commands.values():
            if isinstance(command, CommandGroup):
                print(f"{command.name}:")
            else:
                print(f"  {command.name}: {command.description}")

    @staticmethod
    def exit():
        print("Exiting...")
        exit()

    @staticmethod
    def clear():
        Utils.clear()

    @staticmethod
    def download(subreddit: str, limit: int = 50):
        if not subreddit:
            print("Please specify a subreddit!")
            return
        download(subreddit, limit)

    @staticmethod
    def list(subreddit: str, limit: int = 50):
        if not subreddit:
            print("Please specify a subreddit!")
            return
        list_posts(subreddit, limit)

    @staticmethod
    def open(post_id: int):
        if not post_id:
            print("Please specify a post id!")
            return

    @staticmethod
    def delete(post_id: int):
        if not post_id:
            print("Please specify a post id!")
            return

    @staticmethod
    def sync(subreddit: str):
        if not subreddit:
            print("Please specify a subreddit!")
            return
        print("Syncing...", end="")
        sync_files(subreddit)
        print("done")

    def list_downloaded(self):
        print("Downloaded subreddits:")
        self.db.execute('SELECT name FROM sqlite_master WHERE type="table"')
        for subreddit in [col[0] for col in cur.fetchall()]:
            print(f"/r/\t{subreddit}")

    @staticmethod
    def reset():
        if input("Are you sure you want to do this? (y/n) ").lower() != "y":
            return
        print("Resetting...", end="")
        start_time = time.time()
        os.remove(os.path.join(DATA_DIR, "data.db"))
        print("Deleted database")
        shutil.rmtree(DATA_DIR + "media")
        print("Deleted media directory")
        print("Done ({}s)".format(time.time() - start_time))
        # the database wouldn't exist, so there would probably be errors when anything tries to access it
        print("Exiting...")

    def start(self):
        print("Interactive console mode")
        print("Type 'help' for a list of available commands")
        while True:
            command = input("> ")
            if command == "":
                continue
            if (not (command.split(" ")[0] in self.commands)) \
                    or (isinstance(self.commands[command.split(" ")[0]], CommandGroup)):
                print("Unknown command: {}".format(command))
                continue
            cmd = self.commands[command.split(" ")[0]].func
            if len(signature(cmd).parameters) > len(command.split(" ")[1:]):
                params = list(signature(cmd).parameters)
                params.remove("self") if "self" in params else None
                print("Too few arguments! Expected: {}".format(", ".join(params)))
                continue
            cmd(*command.split(" ")[1:])


if __name__ == "__main__":
    if args.list_subreddits:
        cur.execute('SELECT `name` FROM `sqlite_master` WHERE `type`="table"')
        sub, index = pick([col[0] for col in cur.fetchall()], "Subreddits: ", indicator='>', default_index=0)
        list_posts(sub)
    elif args.interactive:
        console = InteractiveConsole(cur)
        console.start()
    elif args.reset:
        if input("Are you sure you want to do this? (y/n) ").lower() != "y":
            exit()
        print("Resetting...", end="")
        start = time.time()
        os.remove(os.path.join(DATA_DIR, "data.db"))
        print("Deleted database")
        shutil.rmtree(DATA_DIR + "media")
        print("Deleted media directory")
        print("Done ({}s)".format(time.time() - start))
        exit()
    else:
        if args.mode == "download":
            logger.debug("Downloading from %s" % args.sub.replace("/r/", ""))
            download(args.sub, args.limit)
        elif args.mode == "list":
            logger.debug("Listing posts from %s" % args.sub)
            list_posts(args.sub, args.limit)
