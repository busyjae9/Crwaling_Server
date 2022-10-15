from typing import Dict, List, Union
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from flask import Flask
import requests
from models.crawling import CrawlingProduct, CrawlingShop, ProductionCrawlingProduct, ProductionCrawlingShop
from selenium import webdriver
from models import db
from serializers.crawling import CrawlingShopScheme, ProductionCrawlingShopScheme


def kq_store(
    shop: CrawlingShop | ProductionCrawlingShop,
    driver: webdriver.Chrome,
    app: Flask,
    debug: bool,
    categories: List[Dict[str, Union[int, str]]]
):
    with app.app_context():
        id_list = []
        host = 'http://en.kqshop.kr'
        driver.get(shop.url)
        html = driver.page_source
        bs = BeautifulSoup(html, "html.parser")
        menus = bs.find(
            "ul",
            class_="first",
        ).find('dd', class_='first')
        menus_list = menus.find_all("a")

        for menu in menus_list:
            print(menu.text)
            hos_url = host + menu["href"]
            driver.get(hos_url)
            html = driver.page_source
            bs = BeautifulSoup(html, "html.parser")

            pages = bs.find(
                "a", class_="last")

            if pages["href"] == '#none':
                pages = bs.find_all(
                    "li", class_="xans-record-")
                last = pages[-1].find('a')
                last_page = int(
                    last["href"].split("=")[-1]
                )
            else:
                last_page = int(
                    pages["href"].split("=")[-1]
                )
            print(f"마지막 페이지 : {last_page}")

            for p in range(1, last_page + 1):
                driver.get(hos_url+f'&page={p}')
                html = driver.page_source
                bs = BeautifulSoup(html, "html.parser")

                print(f"현재 페이지 : {p}")

                listWrap = bs.find(
                    "div",
                    class_="grid prdList",
                )

                if listWrap is not None:
                    urls = list(
                        map(
                            lambda x: host + x.find('a')["href"],
                            listWrap.find_all(
                                "div", class_="item xans-record-"),
                        )
                    )

                    def find_title(x: BeautifulSoup):
                        title = x.find("span")
                        org_title = ""
                        if title is not None:
                            org_title = title.text

                        return org_title

                    titles = list(
                        map(
                            lambda x: find_title(x),
                            listWrap.find_all("div", class_="name"),
                        )
                    )

                    imgs = list(
                        map(
                            lambda x: "https:" + x["src"],
                            listWrap.find_all("img", class_="prdImg"),
                        )
                    )

                    def find_dc(x: BeautifulSoup):
                        price_parent = x.find(
                            "ul", class_="xans-element- xans-product xans-product-listitem spec")
                        price_list = price_parent.find_all("li")
                        org_price = "0"
                        sale_price = "0"
                        sales = False

                        if len(price_list) == 1:
                            price_was = price_list[0].find("span")
                            price_was = price_was.find("span")
                            org_price = price_was.text.replace("$", '')
                        else:
                            price_was = price_list[0].find("span")
                            price_was = price_was.find("span")
                            org_price = price_was.text.replace("$", '')

                            price_sale = price_list[1].find("span")
                            price_sale = price_sale.find("span")
                            sale_price = price_sale.text.replace("$", '')

                            sales = True

                        activate = True
                        if x.find('img', alt='Out-of-stock'):
                            activate = False

                        return {"org_price": float(org_price), "sale_price": float(sale_price), "sales": sales, "activate": activate}

                    prices = list(
                        map(
                            lambda x: find_dc(x),
                            listWrap.find_all(
                                "div", class_="item xans-record-"),
                        )
                    )

                    print(
                        "products's length is url: {}, title: {}, price: {}, image: {} ".format(
                            len(urls), len(titles), len(prices), len(imgs)
                        )
                    )

                    for url, title, price, img in zip(urls, titles, prices, imgs):
                        params = urlparse(url)
                        id = parse_qs(params.query)['product_no'][0]
                        id = shop.id * 10000000000000 + int(id),
                        id_list.append(id)

                        if debug:
                            db_product = CrawlingProduct.query.get(id)
                        else:
                            db_product = ProductionCrawlingProduct.query.get(
                                id)

                        cates = []

                        for cate in categories:
                            def key_find():
                                if cate["keyword"] == '':
                                    return
                                keywords = cate["keyword"].split(',')
                                for key in keywords:
                                    if key.lower().replace(" ", '') in title.lower().replace(" ", ''):
                                        cates.append(cate)
                                        return
                            key_find()

                        if len(cates) > 0:
                            first_cate = min(
                                cates, key=lambda d: d['priority'])
                            print(first_cate["name"])
                            category = first_cate["name"]
                        else:
                            category = None

                        group = menu.text

                        if db_product is None:
                            if debug:
                                db_product = CrawlingProduct(
                                    id=id,
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=price["activate"],
                                    image=img,
                                    price=price["org_price"],
                                    onSalePrice=price["sale_price"],
                                    onSale=price["sales"],
                                    group=group,
                                    category=category
                                )
                            else:
                                db_product = ProductionCrawlingProduct(
                                    id=id,
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=price["activate"],
                                    image=img,
                                    price=price["org_price"],
                                    onSalePrice=price["sale_price"],
                                    onSale=price["sales"],
                                    group=group,
                                    category=category
                                )
                            db.session.add(db_product)
                            db.session.commit()
                        else:
                            db_product.name = title
                            db_product.productUrl = url
                            db_product.activate = price["activate"]
                            db_product.image = img
                            db_product.price = price["org_price"]
                            db_product.onSalePrice = price["sale_price"]
                            db_product.onSale = price["sales"]
                            db_product.shop = shop
                            db_product.group = group
                            db_product.category = category
                            db.session.commit()

        if debug:
            db_products = CrawlingProduct.query.filter_by(shop=shop)
            db_products = db_products.filter(
                CrawlingProduct.id.notin_(id_list))
            for product in db_products:
                product.activate = False
                db.session.commit()
        else:
            db_products = ProductionCrawlingProduct.query.filter_by(
                shop=shop)
            db_products = db_products.filter(
                ProductionCrawlingProduct.id.notin_(id_list)
            )
            for product in db_products:
                product.activate = False
                db.session.commit()
        driver.quit()

        with app.app_context():
            if debug:
                shop_schema = CrawlingShopScheme()
            else:
                shop_schema = ProductionCrawlingShopScheme()

            res = shop_schema.dump(shop)

            if debug:
                db_product_count = CrawlingProduct.query.filter_by(
                    shop=shop).count()
            else:
                db_product_count = ProductionCrawlingProduct.query.filter_by(
                    shop=shop
                ).count()

            print(db_product_count)

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
