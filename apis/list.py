import json
from threading import Thread

from flask import (
    Response,
    after_this_request,
    make_response,
    request,
)
from flask_restx import Resource, Namespace
import requests
from common.status import Status
from common.utils import Driver, list_shop, refresh_shop, timing_val, validation_limiter
from models.crawling import (
    CrawlingShop,
    ProductionCrawlingShop,
)
from models import db
from app import app
from serializers.crawling import CrawlingShopScheme, ProductionCrawlingShopScheme

from flask_restx import Namespace


List = Namespace("List")


@List.route("")
class ListProduct(Resource):
    @timing_val
    def post(self):  # 멤버 함수의 파라미터로 name 설정
        debug = request.headers.get("debug") == "Yes"
        data = request.get_json()
        res = {"name": "멍청이"}
        res = json.dumps(res, ensure_ascii=False)
        res = make_response(res)

        @after_this_request
        def after_req(res):
            @timing_val
            @res.call_on_close
            def save_task():
                shop = data["shop"]
                category = data["category"]

                def func_list():
                    if shop is not None:
                        with app.app_context():
                            if debug:
                                db_shop = CrawlingShop.query.get(shop["id"])
                            else:
                                db_shop = ProductionCrawlingShop.query.get(
                                    shop["id"])
                            if db_shop is None:
                                if debug:
                                    db_shop = CrawlingShop(
                                        id=shop["id"],
                                        name=shop["name"],
                                        url=shop["url"],
                                    )
                                else:
                                    db_shop = ProductionCrawlingShop(
                                        id=shop["id"],
                                        name=shop["name"],
                                        url=shop["url"],
                                    )
                                db.session.add(db_shop)
                                db.session.commit()
                            else:
                                db_shop.name = shop["name"]
                                db_shop.url = shop["url"]
                                db.session.commit()

                            d = Driver()

                            thread = Thread(
                                target=list_shop,
                                args=[db_shop, d.driver, app, debug, category],
                            )

                            thread.start()

                            # subprocess.call("TASKKILL /f  /IM  CHROMEDRIVER.EXE")
                            # subprocess.call("TASKKILL /f  /IM  CHROME.EXE")

                func_list()

            return res

        return res

    @timing_val
    def get(self):  # 멤버 함수의 파라미터로 name 설정
        data = request.get_json()
        debug = request.headers.get("debug") == "Yes"
        shop = data["shop"]

        @after_this_request
        def after_req(res):
            @res.call_on_close
            @timing_val
            def hook():
                if debug:
                    requests.post(
                        "https://apitest.fanarcade.net/v1/webhook/receive/",
                        json=response_dict,
                    )
                else:
                    requests.post(
                        "https://api.fanarcade.net/v1/webhook/receive/",
                        json=response_dict,
                    )

            return res

        with app.app_context():

            if shop is not None:
                if debug:
                    existed_shop = CrawlingShop.query.get(shop["id"])
                else:
                    existed_shop = ProductionCrawlingShop.query.get(shop["id"])

                if existed_shop is None:
                    return Response(response="Invalid Data", status=Status.invalid)
                else:

                    if debug:
                        shop_schema = CrawlingShopScheme()
                    else:
                        shop_schema = ProductionCrawlingShopScheme()
                    res = shop_schema.dump(existed_shop)
                    response_dict = {
                        "event_type": "SHOP.CRAWLING", "resource": res}

                    response_json = json.dumps(response_dict)
                    return Response(response=response_json, status=Status.ok)
            else:
                return Response(response="Invalid Data", status=Status.invalid)
