from types import SimpleNamespace
import re


# for using within the handlers
REGEXES = {
    "imgur": re.compile(r"^(https?://)?(www\.)?i\.imgur\.com/([a-zA-Z\d]{5,7})(\.[a-zA-Z]{3,4})?$"),
    "gfycat": re.compile(r"^(https?://)?(www\.)?thumbs\.gfycat\.com/.+\.([a-zA-Z\d]{3,4})?$"),
}


def find(html, regex_name):
    matches = REGEXES[regex_name].findall(html)
    if len(matches) == 0:
        return None
    return matches[0]


class SimpleHandlers(SimpleNamespace):
    """
    A class that gets URLs of media from websites with simple design, such as an image directly on the page.
    Other websites like YouTube are handled by yt-dlp.
    """
    @staticmethod
    def imgur(html):
        return find(html, "imgur")

    @staticmethod
    def gfycat(html):
        return find(html, "gfycat")


# for using in other scripts by matching the url
URLS = {
    re.compile(r"^(https?://)(www\.)?imgur.com/gallery/[a-zA-Z\d]{6,7}"): SimpleHandlers.imgur,
    re.compile(r"^(https?://)(www\.)?gfycat.com/.+"): SimpleHandlers.gfycat,  # too lazy to write a stricter regex
}


def get_handler(url):
    """
    Gets the handler for the given url.
    :param url: The url to get the handler for.
    :return: The handler for the given url.
    """
    for regex in URLS:
        if regex.match(url):
            return URLS[regex]
    return None
