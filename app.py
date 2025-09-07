from flask import Flask, render_template, send_from_directory, make_response, request, Response, jsonify, send_file, after_this_request
import os
import tempfile
import traceback

app = Flask(__name__, static_folder="static", template_folder="templates")

# =========================
# Basic Auth 設定
# =========================
REALM = "HarmonyBooster"
USER = os.getenv("BASIC_AUTH_USER", "hbuser")
PASS = os.getenv("BASIC_AUTH_PASS", "hb2025")

# 素通り対象
PUBLIC_PATH_PREFIXES = (
    "/static/",
    "/.well-known/",   # ← 追加：PWA/Chrome関連の自動アクセス
)
PUBLIC_PATHS = (
    "/favicon.ico",
    "/robots.txt",
    "/sw.js",
    "/static/manifest.json",  # ← 追加：manifestは必ず公開
)

def _need_auth():
    return Response("Auth required", 401, {"WWW-Authenticate": f'Basic realm="{REALM}"'})

def _creds_ok(u, p):
    return (u == USER) and (p == PASS)

@app.before_request
def _basic_guard_unified():
    p = request.path or "/"

    # 素通り対象は認証なし
    if p.startswith(PUBLIC_PATH_PREFIXES) or p in PUBLIC_PATHS:
        return

    # それ以外は Basic 認証
    auth = request.authorization
    if not auth or not _creds_ok(auth.username, auth.password):
        return _need_auth()

# 413対策：大きめのアップロードも許可（必要に応じ調整）
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 512  # 512MB

# =========================
# ルーティング
# =========================
@app.route("/")
def index():
    # 認証キャンセルで古いUIが残らないよう no-store
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store"
    return resp

# /sw.js をサイト直下で配信（常に最新を取る）
@app.route("/sw.js")
def service_worker():
    resp = make_response(send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ルートで manifest.json を返す（Basic認証を素通り）
@app.route("/manifest.json")
def manifest_root():
    resp = make_response(
        send_from_directory(app.static_folder, "manifest.json",
                            mimetype="application/manifest+json")
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

# ヘルスチェック（必要なら認証免除にする場合は PUBLIC_PATHS に追加してもよい）
@app.get("/healthz")
def healthz():
    return "ok", 200

# =========================
# 音声処理 API
# =========================
def run_high_quality_process(in_path, out_path, params: dict):
    """
    実処理ロジック：
    ここで本来の高品質処理を呼び出してください。
    例:
        from ms_vocal_attenuator import run_file
        run_file(in_path, out_path,
                 preset=params["preset"],
                 band_low=params["band_low"],
                 band_high=params["band_high"],
                 mid_db=params["mid_db"],
                 side_db=params["side_db"],
                 low_protect=params["low_protect"],
                 high_protect=params["high_protect"],
                 output_db=params["output_db"])
    """
    # 疎通確認用 (必要に応じて置き換え)
    import shutil
    shutil.copyfile(in_path, out_path)

@app.post("/api/process")
def api_process():
    try:
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "ファイルが送られていません"}), 400

        up = request.files["file"]
        if not up or up.filename == "":
            return jsonify({"ok": False, "error": "ファイル名が不正です"}), 400

        # パラメータ（型変換）
        def _f(name, default):
            try:
                return float(request.form.get(name, str(default)))
            except Exception:
                return float(default)

        params = {
            "preset": request.form.get("preset_id") or request.form.get("preset") or "custom",
            "band_low": _f("band_low", 200),
            "band_high": _f("band_high", 6000),
            "mid_db": _f("mid_atten_db", 0),
            "side_db": _f("side_gain_db", 0),
            "low_protect": _f("protect_low_hz", 120),
            "high_protect": _f("protect_high_hz", 8000),
            "output_db": _f("output_gain_db", 0),
        }

        tmpdir = tempfile.mkdtemp(prefix="hb_")
        in_path = os.path.join(tmpdir, "in.tmp")
        out_path = os.path.join(tmpdir, "out.wav")
        up.save(in_path)

        # 実処理
        run_high_quality_process(in_path, out_path, params)

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            return jsonify({"ok": False, "error": "出力ファイルが生成されませんでした"}), 500

        # レスポンス後に掃除
        @after_this_request
        def _cleanup(response):
            try:
                for p in (in_path, out_path):
                    if os.path.exists(p):
                        os.remove(p)
                if os.path.isdir(tmpdir):
                    os.rmdir(tmpdir)
            except Exception:
                pass
            return response

        # 成功時はバイナリで返す
        resp = make_response(send_file(
            out_path,
            mimetype="audio/wav",
            as_attachment=True,
            download_name="HarmonyBooster_out.wav",
            max_age=0,
            conditional=False,
        ))
        # キャッシュさせない
        resp.headers["Cache-Control"] = "no-store"
        return resp

    except Exception as e:
        print("=== /api/process ERROR ===")
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"処理中に例外: {e}"}), 500

# 検索避け
@app.after_request
def add_robots_header(resp):
    resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
