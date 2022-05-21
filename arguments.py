import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Downloads media from a subreddit")
    parser.description = "Downloads a given number of posts from a subreddit for offline viewing."

    # arguments for the command line
    parser.add_argument(
        "-m",
        "--mode",
        help="Mode to run in",
        choices=["download", "list", "sync"],
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

    parser.add_argument(
        "-S",
        "--server",
        action="store_true",
        help="Starts a standalone server to graphically view posts from your browser",
        default=False
    )

    parser.add_argument(
        "-P",
        "--port",
        type=int,
        default=7020,
        help="The port to run the server on, if the server argument is used",
    )

    return parser.parse_args()
