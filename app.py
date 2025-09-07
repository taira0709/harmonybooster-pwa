import os
import tempfile
from flask import Flask, render_template, request, send_file, flash, redirect
from flask import make_response, current_app
from ms_vocal_attenuator import run_file

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            flash("ファイルが選択されていません")
            return redirect("/")
        file = request.files["file"]
        if file.filename == "":
            flash("ファイル名が空です")
            return redirect("/")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_in:
            file.save(temp_in.name)
            input_path = temp_in.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_out:
            output_path = temp_out.name

        try:
            band_low    = float(request.form.get("band_low", 200))
            band_high   = float(request.form.get("band_high", 6000))
            mid_db      = float(request.form.get("mid_atten_db", 0))
            side_db     = float(request.form.get("side_gain_db", 0))
            protect_low = float(request.form.get("protect_low_hz", 150))
            protect_high= float(request.form.get("protect_high_hz", 8000))
            output_db   = float(request.form.get("output_gain_db", 0))

            print(
                f"[PARAMS] band_low={band_low}, band_high={band_high}, "
                f"mid_gain_db={mid_db}, side_gain_db={side_db}, "
                f"output_gain_db={output_db}, protect_low_hz={protect_low}, protect_high_hz={protect_high}",
                flush=True
            )

            run_file(
                in_path=input_path,
                out_path=output_path,
                band_low=band_low,
                band_high=band_high,
                mid_gain_db=mid_db,
                side_gain_db=side_db,
                protect_low_hz=protect_low,
                protect_high_hz=protect_high,
                output_gain_db=output_db,
            )

            return send_file(output_path, as_attachment=True, download_name="processed.wav")

        except Exception as e:
            flash(f"処理エラー: {e}")
            return redirect("/")

    return render_template("index.html")


# ---------- Service Worker 配信（no-cacheで確実に） ----------
@app.route('/sw.js')
def sw_root():
    # static/service-worker.js を確実に読み込み、ブラウザキャッシュを無効化して返す
    path = os.path.join(current_app.static_folder, 'service-worker.js')
    with open(path, 'rb') as f:
        data = f.read()
    resp = make_response(data)
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

# 保険：/static/service-worker.js 直リンクでも同じ内容を返す
@app.route('/static/service-worker.js')
def sw_static_path():
    return sw_root()


# ---------- 診断ルート ----------
@app.route('/_where_static')
def _where_static():
    # いまサーバが参照している static フォルダの絶対パスを表示
    return current_app.static_folder

@app.route('/_ls_static')
def _ls_static():
    # static フォルダの直下ファイル一覧（service-worker.js が出てくるか確認に使う）
    return "<br>".join(os.listdir(current_app.static_folder))


# ---------- 起動ブロック ----------
if __name__ == "__main__":
    import threading, webbrowser, time
    PORT = int(os.environ.get("PORT", "5000"))

    # EXE起動時に既定ブラウザを自動オープン
    def _open_browser():
        time.sleep(1.0)  # サーバーが立ち上がるのを少し待つ
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
        except:
            pass
    threading.Thread(target=_open_browser, daemon=True).start()

    # EXEはバックグラウンドで常駐（コンソール無し）
    app.run(host="0.0.0.0", port=PORT, debug=False)
