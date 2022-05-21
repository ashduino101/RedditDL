# Written by Ashton Fairchild (ashduino101) starting on 2022-04-08
# License: MIT
#
# This program is intended as a command-line application to allow downloading and browsing of Reddit content,
# such as subreddits, posts, and comments.
#

import time
import webbrowser
import shutil
from inspect import signature
from pick import pick

import utils
from utils import *
from constants import *

import media
import url_handler
import server


def get_media_url(post: dict) -> str or None:
    t = url_handler.get_handler(post['url'])
    if t:
        logger.info("Using special URL handler for " + post['url'])
        url = t(requests.get(post['url']).text)
        if url is None:
            logger.error("URL handler returned None")
            return None
        logger.info("URL: " + url)
        return url
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


def download(subreddit: str, limit: int = 50) -> int:

    # sometimes, the limit can be passed as a string, not sure why
    limit = int(limit)

    # check if the sub exists
    if not requests.get(f"https://reddit.com/r/{subreddit}.json",
                        headers=USERAGENT).url == f"https://www.reddit.com/r/{subreddit}.json":
        raise ValueError(f"Subreddit '{subreddit}' does not exist!")

    posts = []

    utils.get_icon(subreddit)

    # we'll use the reddit json api to get the posts
    # first request to get the last id
    data = requests.get(f"https://www.reddit.com/r/{subreddit}.json?count=25", headers=USERAGENT).json()
    for _ in log.progress.range(0, (limit // 25), "Downloading post information"):
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
        f"{len(posts)} posts found ({len(posts) - limit} {'extra' if (len(posts) - limit) > 0 else 'discarded'} posts)"
    )

    # create the media directory for the sub if it doesn't exist
    if not exists(DATA_DIR + f"media/{subreddit}/"):
        logger.info(f"Creating media directory for {subreddit}")
        os.mkdir(DATA_DIR + f"media/{subreddit}/")

    # Download the files
    for i, post in enumerate(posts):
        file = get_media_url(post)
        if file is None:
            logger.info(f"Self-text post {post['title']} (no file)")
            continue

        try:
            cur.execute(
                'INSERT INTO `posts` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    post["id"],
                    post["title"],
                    post["permalink"],
                    post['id'],
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
                     f"media/{subreddit}/{post['id']}")
                    if get_media_url(post)
                    else None
                )
            )
            db.commit()
        except sqlite3.IntegrityError:
            logger.debug(f"Post {post['id']} already exists in database")
            continue
        if file is None:
            logger.error(f"Post {post['id']} has no file")
            continue
        log.progress.request_progress(
            file,
            DATA_DIR + f"media/{subreddit}/{post['id']}",
            f"Downloading post {tc.colored(post['title'], 'blue')} [{tc.colored(post['id'], 'magenta')}]",
        )

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
    subreddits = get_subreddit_list()
    if subreddit not in subreddits:
        r = input(f"You have not downloaded any posts from {subreddit}. "
                  f"Would you like to download posts from it? [Y/n] ") or 'Y'
        if r.lower() == 'y':
            download(subreddit, limit)
        else:
            print("You have not downloaded any posts from this subreddit yet.")
            return []

    post_index = 0
    query = 'SELECT * FROM `posts` WHERE `subreddit` = ?'

    if args.only_nsfw:
        query += " AND `nsfw` = 1"

    # I still don't know how to format this properly, so I'm just going to do it with a lot of if statements
    if args.only_videos:
        query += " AND is_video = 1"

    if args.order_by_score:
        query += " ORDER BY score DESC"

    query += " LIMIT %d" % limit

    logger.debug("Executing query: %s" % query)

    while True:
        cur.execute(query, (subreddit,))
        posts = []
        for row in cur.fetchall():
            posts.append(Post(*row))
        if len(posts) == 0:
            dl = input("You have not downloaded any posts from this subreddit yet. Download them now? [Y/n]") or "y"
            if dl.lower() == "y":
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
                    media.handle_media(post)
                elif c == 'o':
                    webbrowser.open("https://reddit.com" + post.link)


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
        clear()

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

    @staticmethod
    def list_downloaded():
        print("Downloaded subreddits:")
        for subreddit in get_subreddit_list():
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


def get_subreddit_list():
    cur.execute("SELECT DISTINCT `subreddit` FROM `posts`")
    repeating = [col[0] for col in cur.fetchall()]
    return list(set(repeating))


if __name__ == "__main__":
    setup()

    if args.server:
        print("Starting server on port {}".format(args.port))
        server.run(host="127.0.0.1", port=args.port)
        exit()

    if args.list_subreddits:
        subs = get_subreddit_list()
        if subs:
            sub, index = pick(subs, "Subreddits: ", indicator='>', default_index=0)
            list_posts(sub)
        else:
            inp = input("You have not downloaded any posts yet. Download some now? [Y/n]") or "y"
            if inp.lower() == "y":
                inp2 = input("What is the name of the subreddit you want to download from? ")
                download(inp2, args.limit)
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
        elif args.mode == "sync":
            logger.debug("Syncing %s" % args.sub)
            sync_files(args.sub)
