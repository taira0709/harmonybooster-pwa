from flask import Flask, render_template, send_from_directory, make_response, request, Response
import os

app = Flask(__name__, static_folder="static", template_folder="templates")

# ------- Basic Auth (全ルート保護) -------
REALM = "HarmonyBooster"
EXEMPT_PATHS = {"/healthz"}  # すべて保護したいなら set() にする

def _creds_ok(u, p):
    return u == os.getenv("BASIC_AUTH_USER") and p == os.getenv("BASIC_AUTH_PASS")

def _need_auth():
    return Response("Auth required", 401,
                    {"WWW-Authenticate": f'Basic realm="{REALM}"'})

@app.before_request
def _protect():
    if any(request.path.startswith(p) for p in EXEMPT_PATHS):
        return
    auth = request.authorization
    if not auth or not _creds_ok(auth.username, auth.password):
        return _need_auth()

@app.get("/healthz")
def healthz():
    return "ok", 200
# ------- /Basic Auth -------

@app.route("/")
def index():
    # 認証キャンセル時にUIが残らないよう HTML を no-store
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store"
    return resp

# /sw.js をサイト直下で配信（常に最新を取る）
@app.route("/sw.js")
def service_worker():
    resp = make_response(
        send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ついでに検索避け（任意）
@app.after_request
def add_robots_header(resp):
    resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
