import sys
from os.path import exists
from types import SimpleNamespace
import requests
import termcolor as tc
import datetime
import tqdm
import constants


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


class progress(SimpleNamespace):
    @staticmethod
    def request_progress(url: str, target_file: str, message: str):
        bar = "━"
        if exists(target_file):
            print(tc.colored(f"File {target_file} already exists, skipping download", 'yellow'))
        with open(target_file, "wb") as f:
            print(tc.colored(message, "cyan"))
            r = requests.get(url, stream=True, headers=constants.USERAGENT)
            total_length = r.headers.get('content-length')
            if total_length is None:
                f.write(r.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in r.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(50 * dl / total_length)
                    sys.stdout.write(f"\r[{bar * done}{bar * (50 - done)}] {int(100 * dl / total_length)}%")
                    sys.stdout.flush()
        print()

    @staticmethod
    def range(start: int, end: int, message: str):
        return tqdm.tqdm(
            range(start, end),
            desc=message,
            bar_format="{desc} {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt}"
        )
