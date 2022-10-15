from re import T
from flask import (
    Response,
    request,
    redirect,
    url_for,
)  # 서버 구현을 위한 Flask 객체 import

from app import app
import apis
from common.status import Status

app.register_blueprint(apis.blueprint)


@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.ico"))


@app.before_request
def log_details():
    header = request.headers
    please = header.get("CrawlingSever", None)

    if "crawling.fanarcade.net" in request.url or please is not None:
        pass
    else:
        return Response(
            response="authentication_error", status=Status.authentication_error
        )


def run():
    app.run(host='0.0.0.0', port=6584, debug=True, load_dotenv=True)


if __name__ == "__main__":
    run()
