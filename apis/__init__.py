from flask import Blueprint
from flask_restx import Api, Resource

from .list import List
from .refresh import Refresh
from .test import Test


blueprint = Blueprint("api", __name__)

api = Api(blueprint)  # Flask 객체에 Api 객체 등록


@api.route("/hello/<string:name>")  # url pattern으로 name 설정
class HelloWorld(Resource):
    def get(self, name):  # 멤버 함수의 파라미터로 name 설정
        return {"message": "Welcome, %s!" % name}


api.add_namespace(Refresh, "/refresh")
api.add_namespace(List, "/list")
api.add_namespace(Test, "/test")
