# Utilities for ensuring all the files linked in the database are present, making sure the database is up-to-date,
# and fixing any issues.
import os
import constants
from progress.bar import Bar
from os.path import exists


def check_integrity(cur):
    """
    Checks the integrity of the database.
    :param cur: The database to check.
    :return: A list of any files that are missing.
    """
    missing = []
    cur.execute("SELECT `path`, `file_url` FROM `posts`")
    _all = cur.fetchall()
    bar = Bar("Checking integrity", max=len(_all))
    for row in range(len(_all)):
        if not exists(_all[row][0]):
            missing.append(_all[row][1])
        bar.next()
    bar.finish()
    return missing


if __name__ == "__main__":
    print("\n".join(check_integrity(constants.cur)))
