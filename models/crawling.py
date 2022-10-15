from . import db
from sqlalchemy_serializer import SerializerMixin


class CrawlingShop(db.Model, SerializerMixin):
    __tablename__ = "crawling_shop"
    serialize_rules = ("-id",)

    id = db.Column(db.BigInteger, primary_key=True)
    createdDate = db.Column(db.DateTime, server_default=db.func.now())
    modifiedDate = db.Column(
        db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now()
    )
    name = db.Column(db.String(300))
    url = db.Column(db.String())


class CrawlingProduct(db.Model, SerializerMixin):
    __tablename__ = "crawling_product"
    serialize_rules = ("-id",)

    createdDate = db.Column(db.DateTime, server_default=db.func.now())
    modifiedDate = db.Column(
        db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now()
    )
    id = db.Column(db.BigInteger, primary_key=True)
    image = db.Column(db.String())
    name = db.Column(db.String(300))
    category = db.Column(db.String(300))
    group = db.Column(db.String(300))
    member = db.Column(db.String(300))
    productUrl = db.Column(db.String())
    activate = db.Column(db.Boolean(True))
    price = db.Column(db.Float)
    onSalePrice = db.Column(db.Float)
    onSale = db.Column(db.Boolean(True))

    shop = db.relationship("CrawlingShop", backref="product",
                           lazy=True, cascade="all, delete")
    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("crawling_shop.id", ondelete="CASCADE"),
        nullable=True,
    )


class ProductionCrawlingShop(db.Model, SerializerMixin):
    __tablename__ = "production_crawling_shop"
    serialize_rules = ("-id",)

    id = db.Column(db.BigInteger, primary_key=True)
    createdDate = db.Column(db.DateTime, server_default=db.func.now())
    modifiedDate = db.Column(
        db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now()
    )
    name = db.Column(db.String(300))
    url = db.Column(db.String())


class ProductionCrawlingProduct(db.Model, SerializerMixin):
    __tablename__ = "production_crawling_product"
    serialize_rules = ("-id",)

    createdDate = db.Column(db.DateTime, server_default=db.func.now())
    modifiedDate = db.Column(
        db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now()
    )
    id = db.Column(db.BigInteger, primary_key=True)
    image = db.Column(db.String())
    name = db.Column(db.String(300))
    category = db.Column(db.String(300))
    group = db.Column(db.String(300))
    member = db.Column(db.String(300))
    productUrl = db.Column(db.String())
    activate = db.Column(db.Boolean(True))
    price = db.Column(db.Float)
    onSalePrice = db.Column(db.Float)
    onSale = db.Column(db.Boolean(True))

    shop = db.relationship("ProductionCrawlingShop",
                           backref="product", lazy=True, cascade="all, delete")
    shop_id = db.Column(
        db.Integer, db.ForeignKey("production_crawling_shop.id"), nullable=True
    )
