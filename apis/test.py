from flask import request, make_response
from flask_restx import Resource, Api, Namespace
import common.log as log
import json

Test = Namespace("Test")


@Test.route("/<string:name>")  # url pattern으로 name 설정
class TestPost(Resource):
    def get(self, name):  # 멤버 함수의 파라미터로 name 설정
        log.log(request, "Test")

        res = {"name": "멍청이"}
        res = json.dumps(res, ensure_ascii=False)
        res = make_response(res)

        return res
