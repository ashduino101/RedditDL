import subprocess
import time
import moviepy.editor
import cv2
import pygame
from PIL import Image
from utils import *
from constants import term, DATA_DIR, HALF, args
import sys


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


def handle_media(post):
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
        # crossposts, links, etc. return html files that need to be handled with a handler from the directory
        if is_text(one_kb):
            print("Sorry, this post appears to be invalid! "
                  "Please report this on the repository along with the post's ID.")
            return
    if args.cli_media:
        if post.is_video or post.file_url.endswith('.gif'):
            if args.use_purepython_media:
                video(DATA_DIR + f"media/{post.subreddit}/{post.generated_md5}")
            else:
                if sys.platform in constants.CLI_VIDEO_NO_SUPPORT:
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
                w = True
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
                    if (time.time() - start_time > 1) and w:
                        print(
                            term.clear + image(
                                Image.open(
                                    DATA_DIR + f"media/{post.subreddit}/{post.generated_md5}")
                            )
                        )
                        w = False
    else:
        subprocess.call([DATA_DIR + "ffplay", file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
