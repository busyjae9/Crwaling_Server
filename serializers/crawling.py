from models.crawling import (
    CrawlingProduct,
    CrawlingShop,
    ProductionCrawlingProduct,
    ProductionCrawlingShop,
)

from . import ma


class CrawlingProductScheme(ma.SQLAlchemySchema):
    class Meta:
        model = CrawlingProduct

    createdDate = ma.auto_field()
    modifiedDate = ma.auto_field()
    id = ma.auto_field()
    image = ma.auto_field()
    name = ma.auto_field()
    category = ma.auto_field()
    group = ma.auto_field()
    member = ma.auto_field()
    productUrl = ma.auto_field()
    activate = ma.auto_field()
    price = ma.auto_field()
    onSalePrice = ma.auto_field()
    onSale = ma.auto_field()


class CrawlingShopScheme(ma.SQLAlchemySchema):
    class Meta:
        model = CrawlingShop

    id = ma.auto_field()
    name = ma.auto_field()
    createdDate = ma.auto_field()
    modifiedDate = ma.auto_field()
    product = ma.Nested(CrawlingProductScheme, many=True)


class ProductionCrawlingProductScheme(ma.SQLAlchemySchema):
    class Meta:
        model = ProductionCrawlingProduct

    createdDate = ma.auto_field()
    modifiedDate = ma.auto_field()
    id = ma.auto_field()
    image = ma.auto_field()
    name = ma.auto_field()
    category = ma.auto_field()
    group = ma.auto_field()
    member = ma.auto_field()
    productUrl = ma.auto_field()
    activate = ma.auto_field()
    price = ma.auto_field()
    onSalePrice = ma.auto_field()
    onSale = ma.auto_field()


class ProductionCrawlingShopScheme(ma.SQLAlchemySchema):
    class Meta:
        model = ProductionCrawlingShop

    id = ma.auto_field()
    name = ma.auto_field()
    createdDate = ma.auto_field()
    modifiedDate = ma.auto_field()
    product = ma.Nested(ProductionCrawlingProductScheme, many=True)
