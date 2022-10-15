import json
import re
import time
from tkinter import X
from typing import Dict, List, Union
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from flask import Flask
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging
import psutil
from common.kq_store import kq_store


from models.crawling import (
    CrawlingProduct,
    CrawlingShop,
    ProductionCrawlingProduct,
    ProductionCrawlingShop,
)
from models import db
from serializers.crawling import CrawlingShopScheme, ProductionCrawlingShopScheme

selenium_logger = logging.getLogger(
    "selenium.webdriver.remote.remote_connection")
selenium_logger.setLevel(logging.WARNING)


def timing_val(func):
    def wrapper(*arg, **kw):
        t1 = time.time()
        res = func(*arg, **kw)
        t2 = time.time()
        print(
            "func:%r args:[%r, %r] took: %2.4f sec" % (
                func.__name__, arg, kw, t2 - t1)
        )

        return res

    return wrapper


def validation_limiter(methods, validator):
    methods = [name.lower() for name in methods]

    def inner(meth):
        if meth.__name__ not in methods:
            return meth
        return validator(meth)

    return inner


class Driver:
    def __init__(self, headless=True):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("headless")
        options.add_argument("window-size=1920x1080")
        options.add_argument("disable-gpu")
        options.add_argument("disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36"
        )
        prefs = {
            "profile.default_content_setting_values": {
                "cookies": 2,
                "images": 2,
                "plugins": 2,
                "popups": 2,
                "geolocation": 2,
                "notifications": 2,
                "auto_select_certificate": 2,
                "fullscreen": 2,
                "mouselock": 2,
                "mixed_script": 2,
                "media_stream": 2,
                "media_stream_mic": 2,
                "media_stream_camera": 2,
                "protocol_handlers": 2,
                "ppapi_broker": 2,
                "automatic_downloads": 2,
                "midi_sysex": 2,
                "push_messaging": 2,
                "ssl_cert_decisions": 2,
                "metro_switch_to_desktop": 2,
                "protected_media_identifier": 2,
                "app_banner": 2,
                "site_engagement": 2,
                "durable_storage": 2,
            },
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            chrome_options=options,
        )


def refresh_shop(
    obj: dict,
    name: str,
    index: int,
    percent: int,
    driver: webdriver.Chrome,
    db_obj: CrawlingProduct | ProductionCrawlingProduct,
    app: Flask,
    categories: List[Dict[str, Union[int, str]]]
):
    with app.app_context():
        try:
            driver.get(obj["productUrl"])
            html = driver.page_source
        except:
            db_obj.activate = False
            print(f"{percent}% 진행, id: {index}, status : Error_404")
            return

        bs = BeautifulSoup(html, "html.parser")
        activate = True

        if name.replace(" ", "").lower() == "ygselect":
            main = bs.find("div", class_="detailArea")
            if main is None:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_404")
                return

            detail = main.find("div", class_="infoArea")
            heading = detail.find("div", class_="headingArea")

            try:
                image = main.find("img", class_="ThumbImage")
                image_big = main.find("img", class_="BigImage")

                if image_big is not None:
                    db_obj.image = "https:" + image_big["src"]
                elif image is not None:
                    db_obj.image = "https:" + image["src"]
                else:
                    raise
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_image")
                return

            try:
                title_text = heading.find("h2").text
                db_obj.name = title_text

                cates = []

                for cate in categories:
                    def key_find():
                        if cate["keyword"] == '':
                            return
                        keywords = cate["keyword"].split(',')
                        for key in keywords:
                            if key.lower().replace(" ", '') in title_text.lower().replace(" ", ''):
                                cates.append(cate)
                                return
                    key_find()

                if len(cates) > 0:
                    first_cate = min(cates, key=lambda d: d['priority'])
                    print(first_cate["name"])
                    db_obj.category = first_cate["name"]
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_title")
                return

            try:
                price = detail.find("li", rel="Price")
                price_dc = detail.find("li", rel="Discounted Price")

                price = float(".".join(re.findall(r"\d+", price.text)[0:2]))
                if price_dc is None:
                    db_obj.price = price
                    db_obj.onSalePrice = price
                    db_obj.onSale = False

                else:
                    sale_price = float(
                        ".".join(re.findall(r"\d+", price_dc.text)[0:2]))
                    db_obj.price = price
                    db_obj.onSalePrice = sale_price
                    db_obj.onSale = True
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_price")
                return

            try:
                sold_out = heading.find("img", alt="Out-of-stock")
                activate = True
                if sold_out is not None:
                    activate = False

                db_obj.activate = activate
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_soldout")
                return

            print(f"{percent}% 진행, id: {index}, status : Done")
            return

        if name.replace(" ", "").lower() == "smglobalshop":
            main = bs.find(
                "div", class_="product-page product-template prod-product-template"
            )
            if main is None:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_404")
                return

            detail = main.find("script", id="product-json")
            json_data = json.loads(detail.text)

            try:
                title_text = json_data["title"]
                if title_text == "":
                    db_obj.activate = False
                else:
                    db_obj.name = title_text

                db_obj.category = json_data["type"]

                cates = []

                for cate in categories:
                    def key_find():
                        if cate["keyword"] == '':
                            return
                        keywords = cate["keyword"].split(',')
                        for key in keywords:
                            if key.lower().replace(" ", '') in title_text.lower().replace(" ", ''):
                                cates.append(cate)
                                return
                    key_find()

                if len(cates) > 0:
                    first_cate = min(cates, key=lambda d: d['priority'])
                    print(first_cate["name"])
                    db_obj.category = first_cate["name"]

            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_title")
                return

            try:
                image = "https:" + json_data["images"][0]
                db_obj.image = image
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_image")
                return

            try:
                variant = json_data["variants"][0]
                sale_price = variant["price"] / 100
                if variant["compare_at_price"] is None:
                    org_price = sale_price
                    db_obj.onSale = False
                else:
                    org_price = variant["compare_at_price"] / 100
                    db_obj.onSale = True

                db_obj.price = org_price
                db_obj.onSalePrice = sale_price
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_price")
                return

            db_obj.group = json_data["vendor"]

            try:
                available = json_data["available"]
                db_obj.activate = available
            except:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_soldout")
                return

            print(f"{percent}% 진행, id: {index}, status : Done")
            return

        if name.replace(" ", "").lower() == "koreabox":
            template_404 = bs.find("body", class_="template-404")
            main = bs.find("main", class_="main-content")

            if main is None or template_404 is not None:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error_404")
                return

            detail = main.find("div", class_="page-width")
            info_box = detail.find("div", class_="grid product-single")

            title = info_box.find("h1", class_="product-single__title")
            price_info = info_box.find(
                "ul", class_="product-single__meta-list list--no-bullets list--inline"
            )
            not_sale = price_info.find("li", class_="product-tag")
            sale_price = price_info.find(
                "span", class_="product-single__price")
            org_price = price_info.find(
                "s", class_="product-single__price product-single__price--compare"
            )
            sold_out = info_box.find(
                "span", id="AddToCartText-product-template")

            image_container = info_box.find(
                "div",
                class_="product-single__photo product__photo-container product__photo-container-product-template js",
            )

            title_text = title.text.strip()
            if title_text == "":
                activate = False
            else:
                db_obj.name = title_text

            if image_container is not None:
                src = image_container.find("img")["src"]
                image = "https:" + src
                db_obj.image = image
            else:
                activate = False

            if not_sale is None and org_price is None:
                db_obj.price = sale_price.text.replace("$", "")
                db_obj.onSalePrice = sale_price.text.replace("$", "")
                db_obj.onSale = False
            else:
                db_obj.price = org_price.text.replace("$", "")
                db_obj.onSalePrice = sale_price.text.replace("$", "")
                db_obj.onSale = True

            sold_out_text = ""
            if sold_out is None:
                activate = False
            else:
                sold_out_text = sold_out.text.strip().replace(" ", "").lower()
                activate = sold_out_text != "soldout"

            db_obj.activate = activate

            if activate:
                print(f"{percent}% 진행, id: {index}, status : Done")
            else:
                if sold_out_text == "soldout":
                    print(f"{percent}% 진행, id: {index}, status : Error_soldout")
                else:
                    print(f"{percent}% 진행, id: {index}, status : Error_image")
            return

        if name.replace(" ", "").lower() == "ktown4u":
            detail = bs.find("div", class_="detail_area")

            if detail is None:
                db_obj.activate = False
                print(f"{percent}% 진행, id: {index}, status : Error")
                return
            info_box = detail.find("div", class_="sub_section02 info_data_box")
            title = info_box.find("p", class_="goods_tit")
            d_day = title.find("span", class_="tit_d_day")
            if d_day is not None:
                title_text = title.text.replace(d_day.text, "").strip()
            else:
                title_text = title.text.strip()

            if title_text == "":
                activate = False
            else:
                db_obj.name = title_text

            price_dc = info_box.find("div", class_="price_dc")
            price_now = info_box.find("div", class_="price_now")

            image_container = detail.find("div", class_="img_box")

            if image_container is not None:
                src = image_container.find("img")["src"]

                if "jpg" in src:
                    src = re.sub(r"\.\d\.jpg", ".1.jpg", src)
                elif "png" in src:
                    src = re.sub(r"\.\d\.png", ".1.png", src)

                image = "https://www.ktown4u.com" + src

                db_obj.image = image
            else:
                activate = False
                db_obj.image = None

            if price_dc is not None:
                db_obj.price = float(price_dc.find(
                    "span", class_="price").text)
                db_obj.onSalePrice = float(
                    price_now.find("span", class_="price").text)
                db_obj.onSale = True
            elif price_now is not None:
                db_obj.price = float(price_now.find(
                    "span", class_="price").text)
                db_obj.onSalePrice = float(
                    price_now.find("span", class_="price").text)
                db_obj.onSale = False

            db_obj.activate = activate

            if activate:
                print(f"{percent}% 진행, id: {index}, status : Done")
            else:
                print(f"{percent}% 진행, id: {index}, status : Error")
            return


def list_shop(
    shop: CrawlingShop | ProductionCrawlingShop,
    driver: webdriver.Chrome,
    app: Flask,
    debug: bool,
    categories: List[Dict[str, Union[int, str]]]
):

    with app.app_context():
        if shop.name.replace(" ", "").lower() == "interasia":
            driver.quit()

            id_list = []
            page = 1
            while True:
                basic = requests.get(f"{shop.url}&page={page}")
                print(f"{page} 페이지 가져오는 중..")
                html = basic.text
                bs = BeautifulSoup(html, "html.parser")
                pagination = bs.find("div", class_="pagination")
                no_next = (
                    pagination.find(
                        "li", class_="pagination-item pagination-item--next"
                    )
                    is None
                )
                product_list = bs.find("ul", class_="productGrid")
                products = product_list.find_all("li", class_="product")
                for product in products:
                    activate = True

                    photo = product.find("figure", class_="card-figure")

                    url = photo.find("a")["href"]
                    image = photo.find("img")["src"]

                    id = shop.id * 10000000000000 + int(
                        image.split("/")[-2][-(len(str(1000000000000))):]
                    )
                    id_list.append(id)

                    sold_out = photo.find(
                        "div", class_="sale-flag-side sale-flag-side--outstock"
                    )

                    if sold_out is not None:
                        activate = False

                    info = product.find("div", class_="card-body")
                    title = info.find(
                        "h4", class_="card-title").text.replace("\n", "")

                    item_price = info.find(
                        "span", class_="price price--withoutTax price--main"
                    ).text
                    item_sale_price = item_price

                    price = "0"
                    sale_price = "0"
                    onSale = False

                    if item_price is not None and item_sale_price is not None:
                        try:
                            price = float(
                                ".".join(re.findall(r"\d+", item_price)))
                            sale_price = price
                        except:
                            price = 0
                            sale_price = 0
                            activate = False
                    else:
                        activate = False

                    if debug:
                        db_product = CrawlingProduct.query.get(id)
                    else:
                        db_product = ProductionCrawlingProduct.query.get(id)

                    if db_product is None:
                        if debug:
                            db_product = CrawlingProduct(
                                id=id,
                                shop=shop,
                                name=title,
                                productUrl=url,
                                activate=activate,
                                image=image,
                                price=price,
                                onSalePrice=sale_price,
                                onSale=onSale,
                            )

                        else:
                            db_product = ProductionCrawlingProduct(
                                id=id,
                                shop=shop,
                                name=title,
                                productUrl=url,
                                activate=activate,
                                image=image,
                                price=price,
                                onSalePrice=sale_price,
                                onSale=onSale,
                            )
                        db.session.add(db_product)
                        db.session.commit()
                    else:
                        db_product.name = title
                        db_product.productUrl = url
                        db_product.activate = activate
                        db_product.image = image
                        db_product.price = price
                        db_product.onSalePrice = sale_price
                        db_product.onSale = onSale
                        db_product.shop = shop
                        db.session.commit()
                if no_next:
                    break
                else:
                    page += 1

        if shop.name.replace(" ", "").lower() == "withmuu":
            menus_list = [
                f"{shop.url}/goods/goods_list.php?cateCd=003",
                f"{shop.url}/goods/goods_list.php?cateCd=004",
            ]

            id_list = []
            for menu in menus_list:
                try:
                    driver.get(menu)
                    time.sleep(1)
                    html = driver.page_source
                    bs = BeautifulSoup(html, "html.parser")
                    pages = bs.find(
                        "li", class_="btn_page btn_page_last").find("a")
                    last_page = int(
                        pages["href"].split("?")[1].split("&")[0].split("=")[1]
                    )
                    print(f"마지막 페이지 : {last_page}")
                except:
                    return

                for p in range(1, last_page + 1):
                    print(f"{p} 페이지 가져오는 중..")
                    driver.get(f"{menu}&page={p}")
                    html = driver.page_source
                    bs = BeautifulSoup(html, "html.parser")

                    item_gallery = bs.find("div", class_="item_gallery_type")

                    items = item_gallery.find_all("div", class_="item_cont")

                    for item in items:
                        activate = True
                        photo = item.find("div", class_="item_photo_box")
                        info = item.find("div", class_="item_info_cont")

                        url = f"{shop.url}" + \
                            photo.find("a")["href"].replace("..", "")
                        img = photo.find("img")["src"]
                        image = "https://www.withmuu.com" + img

                        title = info.find("strong", class_="item_name").text
                        item_price = info.find(
                            "strong", class_="item_price").text
                        item_sale_price = item_price

                        sold_out = info.find("img", alt="Sold out")
                        if sold_out is not None:
                            activate = False

                        price = 0
                        sale_price = 0
                        onSale = False
                        if item_price is not None and item_sale_price is not None:
                            try:
                                price = float(
                                    ".".join(re.findall(r"\d+", item_price)))
                                sale_price = price
                            except:
                                price = 0
                                sale_price = 0
                                activate = False
                        else:
                            activate = False

                        id = shop.id * 10000000000000 + int(
                            url.split(
                                "goodsNo=")[-1][-(len(str(1000000000000))):]
                        )

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

                        id_list.append(id)

                        if debug:
                            db_product = CrawlingProduct.query.get(id)
                        else:
                            db_product = ProductionCrawlingProduct.query.get(
                                id)

                        if db_product is None:
                            if debug:
                                db_product = CrawlingProduct(
                                    id=id,
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=activate,
                                    image=image,
                                    price=price,
                                    onSalePrice=sale_price,
                                    onSale=onSale,
                                    category=category
                                )

                            else:
                                db_product = ProductionCrawlingProduct(
                                    id=id,
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=activate,
                                    image=image,
                                    price=price,
                                    onSalePrice=sale_price,
                                    onSale=onSale,
                                    category=category
                                )
                            db.session.add(db_product)
                            db.session.commit()
                        else:
                            db_product.name = title
                            db_product.productUrl = url
                            db_product.activate = activate
                            db_product.image = image
                            db_product.price = price
                            db_product.onSalePrice = sale_price
                            db_product.onSale = onSale
                            db_product.shop = shop
                            db.session.commit()

            print(len(id_list))
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

        if shop.name.replace(" ", "").lower() == "ygselect":
            driver.get(shop.url)
            html = driver.page_source
            bs = BeautifulSoup(html, "html.parser")
            menus = bs.find(
                "ul",
                class_="scrollArea",
            )
            menus_list = menus.find_all("a")

            id_list = []
            for menu in menus_list:
                print(menu.text)
                driver.get("https://m.en.ygselect.com" + menu["href"])
                prev_height = 0
                while True:
                    try:
                        button = driver.find_element(By.CLASS_NAME, "moreLink")
                    except:
                        # print("\nThe End Info\n")
                        break
                    driver.execute_script("arguments[0].click();", button)

                    # 페이지 로딩 대기
                    time.sleep(1)

                    driver.execute_script(
                        "window.scrollTo(0,document.body.scrollHeight)"
                    )

                    # 현재 문서 높이를 가져와서 저장
                    curr_height = driver.execute_script(
                        "return document.body.scrollHeight"
                    )

                    if curr_height == prev_height:
                        break
                    elif (psutil.virtual_memory()[1] >> 20) < 800:
                        break
                    else:
                        prev_height = driver.execute_script(
                            "return document.body.scrollHeight"
                        )

                html = driver.page_source
                bs = BeautifulSoup(html, "html.parser")
                listWrap = bs.find(
                    "div",
                    id="productClass",
                )
                listWrap = listWrap.find(
                    "ul",
                    class_="listWrap",
                )

                if listWrap is not None:
                    urls = list(
                        map(
                            lambda x: "https://en.ygselect.com" + x["href"],
                            listWrap.find_all("a", class_="link"),
                        )
                    )
                    titles = list(
                        map(
                            lambda x: x.text,
                            listWrap.find_all("span", class_="ellipTxt"),
                        )
                    )
                    imgs = list(
                        map(
                            lambda x: "https:" + x["src"],
                            listWrap.find_all("img", class_="listPic"),
                        )
                    )

                    def find_dc(x: BeautifulSoup):
                        price = x.find_all("span", class_="price")
                        org_price = "0"
                        if len(price) > 1:
                            for _price in price:
                                if _price["class"] == ["price"]:
                                    org_price = _price.text
                        else:
                            org_price = price[0].text

                        price = float(
                            ".".join(re.findall(r"\d+", org_price)[0:2]))
                        price_dc = x.find("span", class_="price dc")
                        sold_out = x.find("img", class_="icon_img")

                        if price_dc is None:
                            if sold_out is not None:
                                return {
                                    "activate": False,
                                    "sales": False,
                                    "org_price": price,
                                    "sale_price": price,
                                }
                            else:
                                return {
                                    "activate": True,
                                    "sales": False,
                                    "org_price": price,
                                    "sale_price": price,
                                }
                        else:
                            price = float(
                                ".".join(re.findall(
                                    r"\d+", price_dc.text)[0:2])
                            )
                            sale_price = x.find(
                                "span", class_="price stt_discount"
                            ).text
                            sale_price = float(
                                ".".join(re.findall(r"\d+", sale_price)[0:2])
                            )
                            print(sale_price)
                            if sold_out is not None:
                                return {
                                    "activate": False,
                                    "sales": True,
                                    "org_price": price,
                                    "sale_price": sale_price,
                                }
                            else:
                                return {
                                    "activate": True,
                                    "sales": True,
                                    "org_price": price,
                                    "sale_price": sale_price,
                                }

                    prices = list(
                        map(
                            lambda x: find_dc(x),
                            listWrap.find_all("span", class_="listInfo"),
                        )
                    )

                    print(
                        "products's length is url: {}, title: {}, price: {}, image: {} ".format(
                            len(urls), len(titles), len(prices), len(imgs)
                        )
                    )

                    for url, title, price, img in zip(urls, titles, prices, imgs):
                        id = shop.id * 10000000000000 + int(
                            url.split("/")[-6][-(len(str(1000000000000))):]
                        )
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

                        if db_product is None:
                            if debug:
                                db_product = CrawlingProduct(
                                    id=shop.id * 10000000000000
                                    + int(url.split("/")
                                          [-6][-(len(str(1000000000000))):]),
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=price["activate"],
                                    image=img,
                                    price=price["org_price"],
                                    onSalePrice=price["sale_price"],
                                    onSale=price["sales"],
                                    group=menu.text,
                                    category=category
                                )
                            else:
                                db_product = ProductionCrawlingProduct(
                                    id=shop.id * 10000000000000
                                    + int(url.split("/")
                                          [-6][-(len(str(1000000000000))):]),
                                    shop=shop,
                                    name=title,
                                    productUrl=url,
                                    activate=price["activate"],
                                    image=img,
                                    price=price["org_price"],
                                    onSalePrice=price["sale_price"],
                                    onSale=price["sales"],
                                    group=menu.text,
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
                            db_product.group = menu.text
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

        if shop.name.replace(" ", "").lower() == "smglobalshop":
            # 구성 바뀜
            driver.get(shop.url)

            prev_height = 0
            while True:
                try:
                    button = driver.find_element(
                        By.CLASS_NAME, "usf-load-more")
                except:
                    print("\nThe End Info\n")
                    break
                driver.execute_script("arguments[0].click();", button)

                # 페이지 로딩 대기
                time.sleep(1)

                driver.execute_script(
                    "window.scrollTo(0,document.body.scrollHeight)")

                # 현재 문서 높이를 가져와서 저장
                curr_height = driver.execute_script(
                    "return document.body.scrollHeight")
                print("Current Height : {}".format(curr_height))
                print("RAM memory {} used".format(psutil.virtual_memory()[2]))
                print(
                    "Available RAM memory is {}".format(
                        psutil.virtual_memory()[1] >> 20
                    )
                )
                print("CPU {} used".format(psutil.cpu_percent()))

                if curr_height == prev_height:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {} GB".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                elif (psutil.virtual_memory()[1] >> 20) < 800:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {}".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                elif curr_height > 200000:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {}".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                else:
                    prev_height = driver.execute_script(
                        "return document.body.scrollHeight"
                    )

            html = driver.page_source

            bs = BeautifulSoup(html, "html.parser")
            goods_list = bs.find("div", class_="grid_wrapper")
            goods = goods_list.find_all("div", class_="product-index")

            ids = list(
                map(
                    lambda x: shop.id * 10000000000000
                    + int(x["product-selector"][-(len(str(1000000000000))):]),
                    goods,
                )
            )

            urls = list(
                map(lambda x: "https://smglobalshop.com" +
                    x.find("a")["href"], goods)
            )

            titles = list(map(lambda x: x["data-alpha"], goods))

            def find_dc(x: BeautifulSoup):
                no_sale_price = x.find("div", class_="prod-price")
                on_sale_price = x.find("div", class_="onsale")
                on_sale_origin_price = x.find("div", class_="was-listing")
                if no_sale_price is not None:
                    price = float(
                        ".".join(re.findall(r"\d+", no_sale_price.text)[0:2]))
                    return {
                        "sales": False,
                        "org_price": price,
                        "sale_price": price,
                    }
                elif on_sale_price is not None and on_sale_origin_price is not None:
                    on_sale = float(
                        ".".join(re.findall(r"\d+", on_sale_price.text)[0:2])
                    )
                    price = float(
                        ".".join(re.findall(
                            r"\d+", on_sale_origin_price.text)[0:2])
                    )

                    return {
                        "sales": True,
                        "org_price": price,
                        "sale_price": on_sale,
                    }
                else:
                    return {
                        "sales": False,
                        "org_price": float(0),
                        "sale_price": float(0),
                    }

            prices = list(
                map(
                    lambda x: find_dc(x),
                    goods,
                )
            )

            def find_sold_out(x: BeautifulSoup):
                img = x.find("div", class_="reveal")
                sold_out = x.find("div", class_="so icn")
                if sold_out is not None:
                    return {
                        "active": False,
                        "img": "https:" + img.find("img")["data-original"],
                    }
                else:
                    return {
                        "active": True,
                        "img": "https:" + img.find("img")["data-original"],
                    }

            imgs = list(
                map(
                    lambda x: find_sold_out(x),
                    goods,
                )
            )

            id_list = []

            print(
                "products's length is id:{}, url: {}, title: {}, price: {}, image: {}".format(
                    len(ids), len(urls), len(titles), len(prices), len(imgs)
                )
            )

            for id, url, title, price, img in zip(ids, urls, titles, prices, imgs):
                id_list.append(id)

                if debug:
                    db_product = CrawlingProduct.query.get(id)
                else:
                    db_product = ProductionCrawlingProduct.query.get(id)

                if db_product is None:
                    if debug:
                        db_product = CrawlingProduct(
                            id=id,
                            shop=shop,
                            name=title,
                            productUrl=url,
                            activate=img["active"],
                            image=img["img"],
                            price=price["org_price"],
                            onSalePrice=price["sale_price"],
                            onSale=price["sales"],
                        )
                    else:
                        db_product = ProductionCrawlingProduct(
                            id=id,
                            shop=shop,
                            name=title,
                            productUrl=url,
                            activate=img["active"],
                            image=img["img"],
                            price=price["org_price"],
                            onSalePrice=price["sale_price"],
                            onSale=price["sales"],
                        )
                    db.session.add(db_product)
                    db.session.commit()
                else:
                    db_product.name = title
                    db_product.productUrl = url
                    db_product.activate = img["active"]
                    db_product.image = img["img"]
                    db_product.price = price["org_price"]
                    db_product.onSalePrice = price["sale_price"]
                    db_product.onSale = price["sales"]
                    db_product.shop = shop
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

        if shop.name.replace(" ", "").lower() == "fncstore":
            host = 'http://en.fncstore.com'
            driver.get(shop.url)
            html = driver.page_source
            bs = BeautifulSoup(html, "html.parser")
            menus = bs.find(
                "ul",
                class_="depth1",
            )
            menus_list = menus.find_all("a")

            id_list = []
            for menu in menus_list:
                url = host + menu["href"]
                driver.get(url)
                html = driver.page_source
                bs = BeautifulSoup(html, "html.parser")
                pages = bs.find(
                    "a", class_="last")

                if pages["href"] == '#none':
                    pages = bs.find_all(
                        "li", class_="xans-record-")
                    last = pages[-1].find('a')
                    last_page = int(
                        last["href"].split("=")[1]
                    )
                else:
                    last_page = int(
                        pages["href"].split("=")[1]
                    )
                print(f"마지막 페이지 : {last_page}")

                for p in range(1, last_page + 1):
                    driver.get(url+f'/?page={p}')
                    html = driver.page_source
                    bs = BeautifulSoup(html, "html.parser")

                    print(f"현재 페이지 : {p}")

                    listWrap = bs.find(
                        "div",
                        class_="xans-element- xans-product xans-product-listnormal df-prl-wrap df-prl-setup",
                    )

                    print(listWrap is None)

                    if listWrap is not None:
                        urls = list(
                            map(
                                lambda x: host + x["href"],
                                listWrap.find_all(
                                    "a", class_="df-prl-thumb-link"),
                            )
                        )

                        def find_title(x: BeautifulSoup):
                            title = x.find_all("span")
                            org_title = ""
                            if len(title) > 1:
                                org_title = title[1].text
                            else:
                                org_title = title[0].text

                            return org_title

                        titles = list(
                            map(
                                lambda x: find_title(x),
                                listWrap.find_all("a", class_="df-prl-name"),
                            )
                        )

                        imgs = list(
                            map(
                                lambda x: "https:" + x["src"],
                                listWrap.find_all("img", class_="thumb"),
                            )
                        )

                        def find_dc(x: BeautifulSoup):
                            price_parent = x.find(
                                "ul", class_="xans-element- xans-product xans-product-listitem df-prl-listitem")
                            price = price_parent.find_all("span")
                            org_price = "0"
                            if len(price) > 1:
                                org_price = price[1].text.replace("$", '')
                            else:
                                org_price = price[0].text.replace("$", '')

                            activate = True
                            if x.find('img', alt='Out-of-stock'):
                                activate = False

                            return {"org_price": float(org_price), "sale_price": float(org_price), "sales": False, "activate": activate}

                        prices = list(
                            map(
                                lambda x: find_dc(x),
                                listWrap.find_all(
                                    "div", class_="df-prl-fadearea"),
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

                            group = menu.text.strip().split('(')[0]

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

        if shop.name.replace(" ", "").lower() == "linefriends":
            host = 'https://store.linefriends.com'
            driver.get(shop.url)
            html = driver.page_source
            bs = BeautifulSoup(html, "html.parser")

            id_list = []
            group = "BTS"
            category = "BT21"

            def menu_title(x: BeautifulSoup):
                print(x.find('h3').text)

                return {
                    "link": x.find('a')["href"],
                    "title": x.find('h3').text
                }

            menu_list = list(map(
                lambda x: menu_title(x),
                bs.find_all("div", class_="bt21__item"),
            ))

            for menu in menu_list:
                print(menu['title'])
                driver.get(menu['link'])
                html = driver.page_source

                prev_height = 0
                while True:
                    # 페이지 로딩 대기
                    time.sleep(1)

                    driver.execute_script(
                        "window.scrollTo(0,document.body.scrollHeight)"
                    )

                    # 현재 문서 높이를 가져와서 저장
                    curr_height = driver.execute_script(
                        "return document.body.scrollHeight"
                    )

                    if curr_height == prev_height:
                        break
                    elif (psutil.virtual_memory()[1] >> 20) < 800:
                        break
                    else:
                        prev_height = driver.execute_script(
                            "return document.body.scrollHeight"
                        )

                bs = BeautifulSoup(html, "html.parser")

                listWrap = bs.find(
                    "div",
                    class_="product-list collection-matrix clearfix equal-columns--clear equal-columns--outside-trim",
                )

                if listWrap is not None:

                    urls = list(
                        map(
                            lambda x: host + x.find('a')["href"],
                            listWrap.find_all(
                                "div", class_="product-wrap"),
                        )
                    )

                    def find_title(x: BeautifulSoup):
                        title = x.find("span", class_="title")
                        org_title = ""
                        if title is not None:
                            org_title = title.text

                        return org_title

                    titles = list(
                        map(
                            lambda x: find_title(x),
                            listWrap.find_all("div", class_="product-details"),
                        )
                    )

                    imgs = list(
                        map(
                            lambda x: "https:" +
                            x.find('div', class_='image__container').find(
                                'img')["data-src"],
                            listWrap.find_all(
                                "div", class_="product-wrap"),
                        )
                    )

                    def find_dc(x: BeautifulSoup):
                        org_price = "0"
                        sale_price = "0"
                        sales = False
                        activate = True
                        price = x.find("span", class_="price")
                        sold_out = price.find("span", class_="sold_out")

                        if sold_out is not None:
                            activate = False
                        elif price is not None:
                            price = price.find("span", class_="money")
                            price = price.find("span", class_="money")
                            org_price = price.text.replace("$", '')
                            sale_price = price.text.replace("$", '')
                        else:
                            price = x.find("span", class_="price sale")
                            if price is not None:
                                sale_price = price.find("span", class_="money")
                                sale_price = sale_price.find(
                                    "span", class_="money")

                                was_price = price.find(
                                    "span", class_="was_price")
                                was_price = was_price.find(
                                    "span", class_="money")

                                org_price = was_price.text.replace("$", '')
                                sale_price = sale_price.text.replace("$", '')
                                sales = True

                        return {"org_price": float(org_price), "sale_price": float(sale_price), "sales": sales, "activate": activate}

                    prices = list(
                        map(
                            lambda x: find_dc(x),
                            listWrap.find_all(
                                "div", class_="product-details"),
                        )
                    )

                    ids = list(
                        map(
                            lambda x: shop.id * 10000000000000 +
                            int(x["data-id"]),
                            listWrap.find_all(
                                "div", class_="jdgm-widget jdgm-preview-badge jdgm-preview-badge--with-link jdgm--done-setup"),
                        )
                    )

                    print(
                        "products's length is id: {}, url: {}, title: {}, price: {}, image: {} ".format(
                            len(ids), len(urls), len(
                                titles), len(prices), len(imgs)
                        )
                    )

                    for id, url, title, price, img in zip(ids, urls, titles, prices, imgs):
                        id_list.append(id)

                        if debug:
                            db_product = CrawlingProduct.query.get(id)
                        else:
                            db_product = ProductionCrawlingProduct.query.get(
                                id)

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

        if shop.name.replace(" ", "").lower() == "narahomedeco":
            host = 'https://narahomedeco.com'
            menus_list = ["/category/bt21/26/", "/category/titan/237/"]

            id_list = []
            for menu in menus_list:
                host_url = host + menu
                driver.get(host_url)
                html = driver.page_source
                bs = BeautifulSoup(html, "html.parser")

                pagination = bs.find(
                    'div', class_="xans-element- xans-product xans-product-normalpaging ec-base-paginate")
                pages = pagination.find(
                    "a", class_="last")

                if pages["href"] == '#none':
                    pages = pagination.find_all(
                        "li", class_="xans-record-")
                    last = pages[-1].find('a')
                    last_page = int(
                        last["href"].split("page=")[1]
                    )
                else:
                    last_page = int(
                        pages["href"].split("page=")[1]
                    )
                print(f"마지막 페이지 : {last_page}")

                for p in range(1, last_page + 1):
                    driver.get(host_url+f"?page={p}")
                    print(host_url+f"?page={p}")
                    # time.sleep(2)
                    html = driver.page_source
                    bs = BeautifulSoup(html, "html.parser")

                    print(f"현재 페이지 : {p}")

                    if "bt21" in host_url:
                        category = 'BT21'
                    else:
                        category = 'TinyTAN'

                    listWrap = bs.find(
                        "div",
                        class_="xans-element- xans-product xans-product-listnormal ec-base-product",
                    )

                    if listWrap is not None:

                        urls = list(
                            map(
                                lambda x: host + x.find('a')["href"],
                                listWrap.find_all(
                                    "div", class_="thumbnail"),
                            )
                        )

                        def find_title(x: BeautifulSoup):
                            title = x.find_all("span")
                            org_title = ""
                            if len(title) > 1:
                                org_title = title[1].text
                            else:
                                org_title = title[0].text

                            return org_title

                        titles = list(
                            map(
                                lambda x: find_title(x),
                                listWrap.find_all("p", class_="name"),
                            )
                        )

                        imgs = list(
                            map(
                                lambda x: "https:" + x.find('img')["src"],
                                listWrap.find_all("div", class_="thumbnail"),
                            )
                        )

                        def find_dc(x: BeautifulSoup):
                            price = x.find("p", class_="price")
                            org_price = "0"
                            if price is not None:
                                org_price = price.text.replace("$", '')

                            activate = True
                            if x.find('img', alt='Out-of-stock'):
                                activate = False

                            return {"org_price": float(org_price), "sale_price": float(org_price), "sales": False, "activate": activate}

                        prices = list(
                            map(
                                lambda x: find_dc(x),
                                listWrap.find_all(
                                    "div", class_="description"),
                            )
                        )

                        print(
                            "products's length is url: {}, title: {}, price: {}, image: {} ".format(
                                len(urls), len(titles), len(prices), len(imgs)
                            )
                        )

                        for url, title, price, img in zip(urls, titles, prices, imgs):
                            id = url.split('/')[-6]
                            id = shop.id * 10000000000000 + int(id),
                            id_list.append(id)

                            if debug:
                                db_product = CrawlingProduct.query.get(id)
                            else:
                                db_product = ProductionCrawlingProduct.query.get(
                                    id)

                            group = "BTS"

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

        if shop.name.replace(" ", "").lower() == "koreabox":
            driver.quit()

            try:
                basic = requests.get(shop.url)
                html = basic.text
                bs = BeautifulSoup(html, "html.parser")
                pages = bs.find_all("span", class_="page")
                last_page = int(pages[-1].find("a").text)
                print(f"마지막 페이지 : {last_page}")
            except:
                return

            id_list = []
            for p in range(1, last_page + 1):
                page = requests.get(f"{shop.url}&page={p}")
                print(f"{p} 페이지 가져오는 중..")
                html = page.text
                bs = BeautifulSoup(html, "html.parser")
                items = bs.find("script", id="ProductJson-").text
                items = json.loads(items)

                for item in items:
                    activate = item["available"]
                    url = "https://korea-box.com/products/" + item["handle"]
                    title = item["title"]
                    image = "https:" + item["featured_image"]

                    origin_price = item.get('compare_at_price', None)
                    item_price = item.get('price') / 100

                    if origin_price is None or origin_price == 0:
                        price = item_price
                        sale_price = item_price
                        onSale = False
                    else:
                        price = origin_price / 100
                        sale_price = item_price
                        onSale = True
                    id = shop.id * 10000000000000 + int(
                        item["id"]
                    )

                    tags = item.get('tags', None)

                    category = [x for x in tags if 'C:' in x]
                    group = [x for x in tags if 'G:' in x]
                    member = [x for x in tags if 'M:' in x]

                    if len(category) == 0:
                        category = None
                    else:
                        category = category[0].replace('C: ', '')

                    if len(group) == 0:
                        group = None
                    else:
                        group = group[0].replace('G: ', '')

                    if len(member) == 0:
                        member = None
                    else:
                        member = member[0].replace('M: ', '')

                    id_list.append(id)

                    if debug:
                        db_product = CrawlingProduct.query.get(id)
                    else:
                        db_product = ProductionCrawlingProduct.query.get(id)

                    if db_product is None:
                        if debug:
                            db_product = CrawlingProduct(
                                id=id,
                                shop=shop,
                                name=title,
                                productUrl=url,
                                activate=activate,
                                image=image,
                                price=price,
                                onSalePrice=sale_price,
                                onSale=onSale,
                                category=category,
                                group=group,
                                member=member,
                            )

                        else:
                            db_product = ProductionCrawlingProduct(
                                id=id,
                                shop=shop,
                                name=title,
                                productUrl=url,
                                activate=activate,
                                image=image,
                                price=price,
                                onSalePrice=sale_price,
                                onSale=onSale,
                                category=category,
                                group=group,
                                member=member,
                            )
                        db.session.add(db_product)
                        db.session.commit()
                    else:
                        db_product.name = title
                        db_product.productUrl = url
                        db_product.activate = activate
                        db_product.image = image
                        db_product.price = price
                        db_product.onSalePrice = sale_price
                        db_product.onSale = onSale
                        db_product.shop = shop
                        db_product.category = category
                        db_product.group = group
                        db_product.member = member
                        db.session.commit()

            print(len(id_list))
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

        if shop.name.replace(" ", "").lower() == "ktown4u":
            driver.get(shop.url)

            prev_height = 0
            while True:
                try:
                    button = driver.find_element(By.CLASS_NAME, "btn_more")
                except:
                    print("\nThe End Info\n")
                    break
                driver.execute_script("arguments[0].click();", button)

                # 페이지 로딩 대기
                time.sleep(2)

                driver.execute_script(
                    "window.scrollTo(0,document.body.scrollHeight)")

                # 현재 문서 높이를 가져와서 저장
                curr_height = driver.execute_script(
                    "return document.body.scrollHeight")
                print("Current Height : {}".format(curr_height))
                print("RAM memory {} used".format(psutil.virtual_memory()[2]))
                print(
                    "Available RAM memory is {}".format(
                        psutil.virtual_memory()[1] >> 20
                    )
                )
                print("CPU {} used".format(psutil.cpu_percent()))

                if curr_height == prev_height:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {} GB".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                elif (psutil.virtual_memory()[1] >> 20) < 800:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {}".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                elif curr_height > 200000:
                    print("\nThe End Info\n")
                    print("Current Height : {}".format(curr_height))
                    print("RAM memory {} used".format(
                        psutil.virtual_memory()[2]))
                    print(
                        "Available RAM memory is {}".format(
                            psutil.virtual_memory()[1] >> 20
                        )
                    )
                    print("CPU {} used".format(psutil.cpu_percent()))
                    break
                else:
                    prev_height = driver.execute_script(
                        "return document.body.scrollHeight"
                    )

            html = driver.page_source

            bs = BeautifulSoup(html, "html.parser")

            goods_list = bs.find("div", id="goodsList")

            urls = list(
                map(
                    lambda x: "https://www.ktown4u.com" + x["href"],
                    goods_list.find_all("a", class_="list_cont"),
                )
            )

            titles = list(
                map(lambda x: x.text, goods_list.find_all("p", class_="pdt_tit"))
            )

            def find_dc(x: BeautifulSoup):
                dc = x.find("p", class_="dc")
                cost = x.find("span", class_="cost")
                if dc is not None:
                    text = (
                        x.text.replace(dc.text, "")
                        .replace(cost.text, "")
                        .replace("USD ", "")
                        .strip()
                    )

                    if text == "":
                        if cost == "":
                            return {
                                "sales": True,
                                "org_price": float(0),
                                "sale_price": float(0),
                            }
                        else:
                            return {
                                "sales": True,
                                "org_price": float(0),
                                "sale_price": float(cost.text),
                            }
                    else:
                        if cost == "":
                            return {
                                "sales": True,
                                "org_price": float(text),
                                "sale_price": float(0),
                            }
                        else:
                            return {
                                "sales": True,
                                "org_price": float(text),
                                "sale_price": float(cost.text),
                            }
                else:
                    text = x.text.replace("USD ", "").strip()
                    if "KR" in text:
                        text = text.replace(
                            "KRW ", "").replace(",", "").strip()
                        return {
                            "sales": False,
                            "org_price": float(text) / 1250,
                            "sale_price": float(text) / 1250,
                        }
                    else:
                        return {
                            "sales": False,
                            "org_price": float(text),
                            "sale_price": float(text),
                        }

            prices = list(
                map(
                    lambda x: find_dc(x),
                    goods_list.find_all("div", class_="pdt_price"),
                )
            )

            def find_sold_out(x: BeautifulSoup):
                img = x.find("div", class_="inner")
                sold_out = x.find("div", class_="sold_out")
                if sold_out is not None:
                    return {
                        "active": False,
                        "img": "https://www.ktown4u.com" + img.find("img")["data-src"],
                    }
                else:
                    return {
                        "active": True,
                        "img": "https://www.ktown4u.com" + img.find("img")["data-src"],
                    }

            imgs = list(
                map(
                    lambda x: find_sold_out(x),
                    goods_list.find_all("div", class_="thumb"),
                )
            )

            print(
                "products's length is url: {}, title: {}, price: {}, image: {}".format(
                    len(urls), len(titles), len(prices), len(imgs)
                )
            )

            id_list = []

            for url, title, price, img in zip(urls, titles, prices, imgs):
                id = shop.id * 10000000000000 + int(
                    url.replace("https://www.ktown4u.com/iteminfo?goods_no=", "")[
                        -(len(str(1000000000000))):
                    ]
                )

                id_list.append(id)

                if debug:
                    db_product = CrawlingProduct.query.get(id)
                else:
                    db_product = ProductionCrawlingProduct.query.get(id)

                if db_product is None:
                    if debug:
                        db_product = CrawlingProduct(
                            id=id,
                            shop=shop,
                            name=title,
                            productUrl=url,
                            activate=img["active"],
                            image=img["img"],
                            price=price["org_price"],
                            onSalePrice=price["sale_price"],
                            onSale=price["sales"],
                        )
                    else:
                        db_product = ProductionCrawlingProduct(
                            id=id,
                            shop=shop,
                            name=title,
                            productUrl=url,
                            activate=img["active"],
                            image=img["img"],
                            price=price["org_price"],
                            onSalePrice=price["sale_price"],
                            onSale=price["sales"],
                        )
                    db.session.add(db_product)
                    db.session.commit()
                else:
                    db_product.name = title
                    db_product.productUrl = url
                    db_product.activate = img["active"]
                    db_product.image = img["img"]
                    db_product.price = price["org_price"]
                    db_product.onSalePrice = price["sale_price"]
                    db_product.onSale = price["sales"]
                    db_product.shop = shop
                    db.session.commit()

            print(len(id_list))
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

        if shop.name.replace(" ", "").lower() == "kqshop":
            return kq_store(shop,
                            driver,
                            app,
                            debug,
                            categories)

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
