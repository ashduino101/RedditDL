import requests
import re
import media_handler


def get_file_url(file_id: str) -> str:
    return "".join(
        re.findall(
            r"(https://cdn-\d*.anonfiles.com/)(\w{10})(/[\w-]{19}/)(.*)\"",
            requests.get("https://www.anonfiles.com/" + file_id).text
        )[0]
    )


def get_handler(url: str) -> str or None:
    for key, value in media_handler.URLS.items():
        if key.match(url):
            return value
    return None
