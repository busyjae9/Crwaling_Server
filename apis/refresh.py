import json
import subprocess
import time
import os

from threading import Thread
from flask import Response, after_this_request, make_response, request
from flask_restx import Resource, Namespace
import requests
from common.status import Status
from common.utils import Driver, list_shop, refresh_shop, timing_val, validation_limiter
from models.crawling import (
    CrawlingProduct,
    CrawlingShop,
    ProductionCrawlingProduct,
    ProductionCrawlingShop,
)
from models import db
from app import app

from serializers.crawling import CrawlingShopScheme, ProductionCrawlingShopScheme

Refresh = Namespace("Refresh")


@Refresh.route("")
class RefreshProduct(Resource):
    @timing_val
    def post(self):  # 멤버 함수의 파라미터로 name 설정
        debug = request.headers.get("debug") == "Yes"
        data = request.get_json()
        res = {"name": "멍청이"}
        res = json.dumps(res, ensure_ascii=False)
        res = make_response(res)

        @after_this_request
        def after_req(res):
            @res.call_on_close
            @timing_val
            def save_task():
                shop = data["shop"]
                products = data["products"]
                category = data["category"]

                def func_refresh():
                    with app.app_context():
                        print("products: " + str(len(products)))
                        if shop is not None and products is not None:
                            if debug:
                                db_shop = CrawlingShop.query.get(shop["id"])
                            else:
                                db_shop = ProductionCrawlingShop.query.get(
                                    shop["id"])

                            if db_shop is None:
                                if debug:
                                    db_shop = CrawlingShop(
                                        id=shop["id"], name=shop["name"]
                                    )
                                else:
                                    db_shop = ProductionCrawlingShop(
                                        id=shop["id"], name=shop["name"]
                                    )
                                db.session.add(db_shop)
                                db.session.commit()
                            else:
                                db_shop.name = shop["name"]
                                db.session.commit()

                            threads = []
                            drivers = []

                            def input_driver():
                                d = Driver()
                                drivers.append(d)

                            for i, v in enumerate(range(os.cpu_count())):
                                thread_func = Thread(target=input_driver)
                                thread_func.start()
                                if (i + 1) % len(
                                    range((round(os.cpu_count())))
                                ) / 2 == 0:
                                    thread_func.join()
                                elif (i + 1) == len(range(os.cpu_count())):
                                    thread_func.join()

                            time.sleep(2)

                            print("workers: " + str(len(drivers)))

                            for index, product in enumerate(products):
                                if debug:
                                    db_product = CrawlingProduct.query.get(
                                        product["id"]
                                    )
                                else:
                                    db_product = ProductionCrawlingProduct.query.get(
                                        product["id"]
                                    )

                                if db_product is None:
                                    if debug:
                                        db_product = CrawlingProduct(
                                            id=product["id"],
                                            shop=db_shop,
                                            name=product["name"],
                                            productUrl=product["productUrl"],
                                            activate=product["activate"],
                                            price=product["price"],
                                            onSalePrice=product["onSalePrice"],
                                            onSale=product["onSale"],
                                        )
                                    else:
                                        db_product = ProductionCrawlingProduct(
                                            id=product["id"],
                                            shop=db_shop,
                                            name=product["name"],
                                            productUrl=product["productUrl"],
                                            activate=product["activate"],
                                            price=product["price"],
                                            onSalePrice=product["onSalePrice"],
                                            onSale=product["onSale"],
                                        )
                                    db.session.add(db_product)
                                    db.session.commit()
                                else:
                                    db_product.name = product["name"]
                                    db_product.productUrl = product["productUrl"]
                                    db_product.activate = product["activate"]
                                    db_product.price = product["price"]
                                    db_product.onSalePrice = product["onSalePrice"]
                                    db_product.onSale = product["onSale"]
                                    db_product.shop = db_shop
                                    db.session.commit()

                                thread = Thread(
                                    target=refresh_shop,
                                    args=[
                                        product,
                                        shop["name"],
                                        product["id"],
                                        round(
                                            number=(
                                                index / len(products)) * 100,
                                            ndigits=2,
                                        ),
                                        drivers[(index + 1) %
                                                len(drivers)].driver,
                                        db_product,
                                        app,
                                        category
                                    ],
                                )
                                threads.append(thread)

                            for index, thread in enumerate(threads):
                                thread.start()
                                # thread.join()

                                if (index + 1) % (len(drivers) / 2) == 0:
                                    thread.join()
                                elif index + 1 == len(threads):
                                    thread.join()

                            time.sleep(6)

                            db.session.commit()

                            print("\nTHREAD DONE")

                            for driver in drivers:
                                driver.driver.quit()

                            if debug:
                                shop_schema = CrawlingShopScheme()
                            else:
                                shop_schema = ProductionCrawlingShopScheme()

                            if debug:
                                db_product_count = CrawlingProduct.query.filter_by(
                                    shop=db_shop
                                ).count()
                            else:
                                db_product_count = (
                                    ProductionCrawlingProduct.query.filter_by(
                                        shop=db_shop
                                    ).count()
                                )

                            res = shop_schema.dump(db_shop)
                            response_dict = {
                                "event_type": "SHOP.CRAWLING",
                                "resource": res,
                                "count": db_product_count,
                            }

                            if debug:
                                res = requests.post(
                                    "https://apitest.fanarcade.net/v1/webhook/receive/",
                                    json=response_dict,
                                )
                            else:
                                res = requests.post(
                                    "https://api.fanarcade.net/v1/webhook/receive/",
                                    json=response_dict,
                                )

                            print(res)
                            # subprocess.call("TASKKILL /f  /IM  CHROMEDRIVER.EXE")
                            # subprocess.call("TASKKILL /f  /IM  CHROME.EXE")

                func_refresh()

            return res

        return res

    @timing_val
    def get(self):  # 멤버 함수의 파라미터로 name 설정
        data = request.get_json()
        debug = request.headers.get("debug") == "Yes"
        shop = data["shop"]
        method = data["method"]

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

                    if debug:
                        db_product_count = CrawlingProduct.query.filter_by(
                            shop=existed_shop
                        ).count()
                    else:
                        db_product_count = ProductionCrawlingProduct.query.filter_by(
                            shop=existed_shop
                        ).count()

                    res = shop_schema.dump(existed_shop)
                    response_dict = {
                        "event_type": "SHOP.CRAWLING",
                        "resource": res,
                        "count": db_product_count,
                    }

                    response_json = json.dumps(response_dict)
                    return Response(response=response_json, status=Status.ok)
            else:
                return Response(response="Invalid Data", status=Status.invalid)

    @timing_val
    def delete(self):
        data = request.get_json()
        debug = request.headers.get("debug") == "Yes"
        shop = data["shop"]
        with app.app_context():
            try:
                if debug:
                    existed_shop = CrawlingShop.query.get(shop["id"])
                    if existed_shop is None:
                        existed_shop = CrawlingShop.query.filter_by(
                            name=shop["name"]
                        ).first()
                else:
                    existed_shop = ProductionCrawlingShop.query.get(shop["id"])
                    if existed_shop is None:
                        existed_shop = ProductionCrawlingShop.query.filter_by(
                            name=shop["name"]
                        ).first()
                print(existed_shop)

                if existed_shop is not None:
                    db.session.delete(existed_shop)
                    db.session.commit()

                    if debug:
                        deleted_shop = CrawlingShop.query.get(shop["id"])
                        if deleted_shop is None:
                            deleted_shop = CrawlingShop.query.filter_by(
                                name=shop["name"]
                            ).first()
                    else:
                        deleted_shop = ProductionCrawlingShop.query.get(
                            shop["id"])
                        if deleted_shop is None:
                            deleted_shop = ProductionCrawlingShop.query.filter_by(
                                name=shop["name"]
                            ).first()

                    print(deleted_shop)

                    if deleted_shop is not None:
                        return Response("did not delete", status=Status.invalid)
                    else:
                        return Response("good", status=Status.ok)
                else:
                    return Response("already delete", status=Status.ok)
            except:
                return Response("invalid", status=Status.invalid)
