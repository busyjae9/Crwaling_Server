from flask import Flask
import common.config as config
from flask_migrate import Migrate
from serializers import ma
from models import *

migrate = Migrate(compare_type=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_CONNECTION_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_AS_ASCII"] = False

app.app_context().push()

db.init_app(app)
ma.init_app(app)
migrate.init_app(app, db)
db.create_all()
    

