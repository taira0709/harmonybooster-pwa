from flask import Flask, render_template, send_from_directory, make_response
import os

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.route("/")
def index():
    return render_template("index.html")

# /sw.js をサイトルートで配信
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
