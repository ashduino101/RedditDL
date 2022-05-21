import io
import os
import re
import stat
from itertools import chain
from os.path import exists
from html import unescape

import PIL
from PIL import Image, ImageFilter
import requests
import termcolor as tc
import constants
from constants import logger, cur, db
import cv2


def build_query(query_type: str, table: str, values: tuple or list = None, where: dict = None,
                order_by: str = None, limit: int = None, offset: int = None):
    query = query_type.upper() + " INTO " + table + "VALUES (" + ", ".join(values) + ") "
    if where:
        query += "WHERE "
        for key, value in where.items():
            query += key + " = " + str(value) + " AND "
        query = query[:-5]
    if order_by:
        query += "ORDER BY " + order_by + " "
    if limit:
        query += "LIMIT " + str(limit) + " "
    if offset:
        query += "OFFSET " + str(offset) + " "
    return query


def progress_bar(percent, width=50, color="green", bg="gray"):
    # the formatting isn't great, but it works
    return tc.colored(
        constants.LINE, color
    ) * int(percent * width // 100) + tc.colored(
        constants.LINE, bg
    ) * (width - int(percent * width // 100)) + " " + str(percent) + "%"


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def is_text(_bytes):
    return not bool(_bytes.translate(None, constants.TEXT_CHARS))


# modified from https://github.com/acifani/boxing/blob/master/boxing/boxing.py
def boxing(texts: list, style: str = 'single') -> str:
    chars = constants.boxes.get(style, constants.boxes['single'])
    longest = str(list(reversed(sorted(list(chain.from_iterable([t.splitlines() for t in texts])), key=len)))[0])

    def ansi_escape(t: str) -> str:
        regex = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        return regex.sub('', t)

    max_line_len = max(map(lambda l: len(ansi_escape(l)), longest.splitlines()))
    final = ""
    for i, text in enumerate(texts):
        lines = text.splitlines()
        horizontal_margin = ' ' * 3
        horizontal_padding = ' ' * 3
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
        vertical_padding = '\n' + left + ' ' * max_line_len + right
        top = top_bar + vertical_padding
        middle = ''
        for line in lines:
            fill = ' ' * (max_line_len - len(ansi_escape(line)))
            middle += '\n' + left + line + fill + right
        bottom = vertical_padding + '\n' + bottom_bar
        final += top + middle + bottom

    return final


def sync_files(subreddit: str):
    if not os.path.exists(constants.DATA_DIR + f"media/{subreddit}"):
        os.mkdir(constants.DATA_DIR + f"media/{subreddit}")

    cur.execute('SELECT `file_url`, `path` FROM `%s`' % subreddit)
    for row in cur.fetchall():
        if not exists(row[1]):
            with open(row[1], 'wb') as file:
                file.write(requests.get(row[0]).content)
                logger.info("Downloaded %s to %s" % (row[0], row[1]))


def setup():
    # create the data directory if it doesn't exist
    if not exists(constants.DATA_DIR):
        logger.debug("Creating data directory")
        os.mkdir(constants.DATA_DIR)

    # create the icons directory if it doesn't exist
    if not exists(constants.DATA_DIR + "icons"):
        logger.debug("Creating icons directory")
        os.mkdir(constants.DATA_DIR + "icons")

    # create the directory for all the files if it doesn't exist (files are stored in the filesystem for performance)
    if not exists(constants.DATA_DIR + "media"):
        logger.debug("Creating media directory")
        os.mkdir(constants.DATA_DIR + "media")

    # download terminal video player if it hasn't been downloaded yet
    if not exists(constants.DATA_DIR + "tvp"):
        logger.debug("Downloading tvp")
        with open(constants.DATA_DIR + "tvp", "wb") as f:
            f.write(requests.get(constants.TVP_FILE_LINUX).content)
            st = os.stat(constants.DATA_DIR + "tvp")
            # chmod the file so that it can be executed (doesn't do it by default)
            os.chmod(constants.DATA_DIR + "tvp", st.st_mode | stat.S_IEXEC)

    # download ffplay for linux or windows if it hasn't been downloaded yet
    if not (exists(constants.DATA_DIR + "ffplay") or exists(constants.DATA_DIR + "ffplay.exe")):
        if constants.PLATFORM == 'linux':
            logger.debug("Downloading ffplay")
            with open(constants.DATA_DIR + "ffplay", "wb") as f:
                # linux
                resp = requests.get(constants.FFPLAY_FILE_LINUX)
                if resp.status_code == 200:
                    f.write(resp.content)
                    st = os.stat(constants.DATA_DIR + "ffplay")
                    # for some reason, the file isn't executable by default, though it should be
                    os.chmod(constants.DATA_DIR + "ffplay", st.st_mode | stat.S_IEXEC)
                else:
                    logger.error("Failed to download ffplay. Non-CLI video playback will not function.")

        elif constants.PLATFORM == 'win32':
            logger.debug("Downloading ffplay")
            with open(constants.DATA_DIR + "ffplay.exe", "wb") as f:
                # windows
                resp = requests.get(constants.FFPLAY_FILE_WIN)
                if resp.status_code == 200:
                    # make sure the download worked, in case anonfile is down or something
                    f.write(resp.content)
                else:
                    logger.error("Failed to download ffplay. Video playback will not function.")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `posts` (
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
        """
    )

    db.commit()


def truefalse(s):
    if s == "false" or s == 0:
        return False
    else:
        return True


def get_icon(subreddit):
    file = constants.DATA_DIR + "icons/" + subreddit + ".jpg"
    if exists(file):
        if os.stat(file).st_size > 0:
            return file
        else:
            return None
    else:
        try:
            with open(file, "wb") as f:
                data = requests.get(
                    "https://www.reddit.com/r/" + subreddit + "/about.json", headers=constants.USERAGENT
                ).json()["data"]
                if data["community_icon"]:
                    f.write(requests.get(unescape(data["community_icon"]), headers=constants.USERAGENT).content)
                    return file
                elif data["icon_img"]:  # we use the icon_img as a fallback
                    f.write(requests.get(unescape(data["icon_img"]), headers=constants.USERAGENT).content)
                    return file
                else:
                    return None
        except KeyError:
            return None


def media_thumbnail(filepath, width=256, height=256, blur=False):
    if not exists(filepath):
        return 404
    try:
        im = Image.open(filepath).convert('RGB')
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(radius=50))
        im.thumbnail((width, height))
        im_bytes = io.BytesIO()
        im.save(im_bytes, format="JPEG")
        im_bytes.seek(0)
        return im_bytes.read()
    except (PIL.UnidentifiedImageError, ValueError):
        cap = cv2.VideoCapture(filepath)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                is_success, im_buf_arr = cv2.imencode(".jpg", frame)
                if not is_success:
                    return 500
                byte_im = io.BytesIO(im_buf_arr.tobytes())
                im = Image.open(byte_im).convert("RGB")
                if blur:
                    im = im.filter(ImageFilter.GaussianBlur(radius=50))
                im.thumbnail((width, height))
                im_bytes = io.BytesIO()
                im.save(im_bytes, format="JPEG")
                im_bytes.seek(0)
                return im_bytes.read()
            else:
                return 500
        else:
            return 500
