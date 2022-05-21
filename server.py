import io
from os.path import exists

import magic
import PIL
import flask
import sqlite3
from constants import DATA_DIR
from utils import truefalse, get_icon, media_thumbnail
from PIL import Image, ImageFilter

app = flask.Flask(__name__, template_folder="www")


# if you want to add something to the script, please throw the correct HTTP error code if something goes wrong:
# 200: OK
# 201: Created
# 202: Accepted
# 203: Non-Authoritative Information
# 204: No Content
# 205: Reset Content
# 206: Partial Content
# 207: Multi-Status
# 208: Already Reported
# 226: IM Used

# 300: Multiple Choices
# 301: Moved Permanently
# 302: Found
# 303: See Other
# 304: Not Modified
# 305: Use Proxy
# 306: Switch Proxy
# 307: Temporary Redirect
# 308: Permanent Redirect

# 400: Bad Request
# 401: Unauthorized
# 402: Payment Required
# 403: Forbidden
# 404: Not Found
# 405: Method Not Allowed
# 406: Not Acceptable
# 407: Proxy Authentication Required
# 408: Request Timeout
# 409: Conflict
# 410: Gone
# 411: Length Required
# 412: Precondition Failed
# 413: Payload Too Large
# 414: URI Too Long
# 415: Unsupported Media Type
# 416: Range Not Satisfiable
# 417: Expectation Failed
# 418: I'm a teapot
# 421: Misdirected Request
# 422: Unprocessable Entity
# 423: Locked
# 424: Failed Dependency
# 426: Upgrade Required
# 428: Precondition Required
# 429: Too Many Requests
# 431: Request Header Fields Too Large
# 451: Unavailable For Legal Reasons

# 500: Internal Server Error
# 501: Not Implemented
# 502: Bad Gateway
# 503: Service Unavailable
# 504: Gateway Timeout
# 505: HTTP Version Not Supported
# 506: Variant Also Negotiates
# 507: Insufficient Storage
# 508: Loop Detected
# 510: Not Extended
# 511: Network Authentication Required


@app.route("/api/icon/<subreddit>", methods=["GET"])
def icon(subreddit):
    f = get_icon(subreddit)
    if f:
        with open(f, "rb") as f:
            return flask.Response(f.read(), mimetype="image/jpeg")
    else:
        return "", 404


@app.route("/api/get_posts", methods=["GET"])
def get_posts():
    with sqlite3.connect(DATA_DIR + "/data.db") as conn:  # we must connect every page since sqlite3 isn't thread-safe
        cur = conn.cursor()

    args = flask.request.args
    if "offset" in args:
        offset = int(args["offset"])
    else:
        offset = 0
    if "limit" in args:
        limit = int(args["limit"])
    else:
        limit = 25
    if "random" in args:
        print("random in args")
        order = "RANDOM()"
    else:
        order = "`time` DESC"
    if "subreddit" in args:
        cur.execute(
            "SELECT * FROM posts WHERE subreddit = ? ORDER BY %s LIMIT ? OFFSET ?" % order,
            (
                args["subreddit"],
                limit,
                offset
            )
        )
    else:
        cur.execute("SELECT * FROM `posts` ORDER BY %s LIMIT ? OFFSET ?" % order, (limit, offset))

    post_list = []
    posts = cur.fetchall()
    for _post in posts:
        post_list.append({
            "id": _post[0],
            "title": _post[1],
            "permalink": _post[2],
            "md5": _post[3],
            "author": _post[4],
            "time_created": _post[5],
            "type": _post[6],
            "url": _post[7],
            "is_video": truefalse(_post[8]),
            "is_nsfw": truefalse(_post[9]),
            "is_spoiler": truefalse(_post[10]),
            "score": _post[11],
            "vote_ratio": _post[12],
            "subreddit": _post[13]
        })

    return flask.jsonify(post_list)


@app.route("/api/get_media/<subreddit>/<md5>", methods=["GET"])
def get_media(subreddit, md5):
    args = flask.request.args
    file = DATA_DIR + "/media/" + subreddit + "/" + md5
    if not exists(file):
        return "", 404
    if "blur" in args:
        try:
            im = Image.open(file)
            im = im.filter(ImageFilter.GaussianBlur(radius=50))
            output = io.BytesIO()
            im.save(output, format='JPEG')
            output.seek(0)
            return flask.Response(output.read(), mimetype="image/jpeg")
        except (PIL.UnidentifiedImageError, ValueError):
            pass
    with open(file, "rb") as f:
        mime = magic.Magic(mime=True)
        return flask.Response(f.read(), mimetype=mime.from_file(file))


@app.route("/api/thumbnail/<subreddit>/<md5>", methods=["GET"])
def thumbnail(subreddit, md5):
    args = flask.request.args
    file = DATA_DIR + "/media/" + subreddit + "/" + md5
    if not exists(file):
        return "", 404
    if "blur" in args:
        blur = True
    else:
        blur = False
    resp = media_thumbnail(file, blur=blur, width=512, height=512)
    if isinstance(resp, int):
        return "", resp
    return flask.Response(resp, mimetype="image/jpeg")


@app.route("/", methods=["GET"])
def index():
    return flask.render_template("index.html")


@app.route("/r/<subreddit>", methods=["GET"])
def sub(subreddit):
    return flask.render_template("subreddit.html", subreddit=subreddit)


@app.route("/r/<subreddit>/<post_id>/", methods=["GET"])
def post(subreddit, post_id):
    with sqlite3.connect(DATA_DIR + "/data.db") as conn:
        cur = conn.cursor()
    cur.execute("SELECT * FROM `posts` WHERE `subreddit` = ? AND `id` = ? LIMIT 1", (subreddit, post_id))
    res = cur.fetchall()
    md5 = res[0][3]
    is_video = res[0][8]
    if not is_video:
        return "<img src='/api/get_media/" + subreddit + "/" + md5 + "'></img>"
    else:
        return "<video src='/api/get_media/" + subreddit + "/" + md5 + "' controls></video>"


run = app.run


if __name__ == "__main__":  # for testing
    run(host="127.0.0.1", port=7020, debug=True)
