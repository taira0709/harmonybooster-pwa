from flask import Flask, render_template, send_from_directory, make_response, request, Response
import os

app = Flask(__name__, static_folder="static", template_folder="templates")

# ------- Basic Auth (全ルート保護) -------
REALM = "HarmonyBooster"
EXEMPT_PATHS = {"/healthz"}  # 認証不要にしたいパスがあればここに追加

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
    return render_template("index.html")

# /sw.js をサイトルートで配信（キャッシュ無効化ヘッダ付き）
@app.route("/sw.js")
def service_worker():
    resp = make_response(
        send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
