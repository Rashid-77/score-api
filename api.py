#!/usr/bin/env python

import datetime
import hashlib
import json
import logging
import re
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from optparse import OptionParser

from scoring import get_interests, get_score

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}
MAX_AGE = 70


class Field:
    def __init__(self, required, nullable):
        self.required = required
        self.nullable = nullable
        self.name = None
        self.value = None

    def __set__(self, instance, value):
        if self.required is True and value is None:
            raise ValueError(f'Value "{self.__str__()}" are required')
        if self.nullable is False and not value:
            raise ValueError(f'Value "{self.__str__()}" is empty')
        if self.nullable is True and value is None:
            setattr(instance, self.name, None)
            return
        self.validate(value)
        setattr(instance, self.name, value)

    def validate(self):
        pass

    def __get__(self, instance, cls):
        return getattr(instance, self.name)

    def __set_name__(self, obj, name):
        self.name = "_" + name

    def __str__(self):
        return self.name[1:]


class CharField(Field):
    def validate(self, val):
        if not isinstance(val, str):
            raise ValueError(f"Value {val} have to be str, not {type(val)}")


class ArgumentsField(Field):
    def validate(self, val):
        if not isinstance(val, dict):
            raise ValueError(f"Argument {val} have to be dict, not {type(val)}")
        return val


class EmailField(CharField):
    def validate(self, val):
        super().validate(val)
        if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", val):
            raise ValueError("Email should contain @. See RFC 5322")
        return val


class PhoneField(Field):
    """Phone field should be str or int type,
    should be 11 symbols length and start with 7"""

    def validate(self, val):
        if not (isinstance(val, (int, str))):
            raise ValueError("Phone number shoud be int or str")
        if not re.match(r"^7[0-9]{10}$", str(val)):
            raise ValueError("Phone number must be 11 symbols length and start with 7")
        return val


class DateField(CharField):
    """Field must be date in DD.MM.YYYY format."""

    def validate(self, val):
        super().validate(val)
        try:
            return datetime.datetime.strptime(val, "%d.%m.%Y")
        except ValueError:
            raise ValueError("Field must be date in DD.MM.YYYY format.")


class BirthDayField(DateField):
    def __init__(self, required, nullable, max_age=MAX_AGE):
        super().__init__(required, nullable)
        self.max_age = max_age

    def validate(self, val):
        self.value = super().validate(val)
        if self.is_old():
            raise ValueError("Age must be less than 70 years.")
        return val

    def is_old(self) -> bool:
        today = date.today()
        bd = self.value
        not_a_full_year = (today.month, today.day) < (bd.month, bd.day)
        age = today.year - bd.year - not_a_full_year
        return age >= self.max_age


class GenderField(Field):
    def validate(self, val):
        if not isinstance(val, int):
            raise ValueError(f"Value should be int, not {type(val)}")
        elif val not in GENDERS:
            values = ", ".join(str(v) for v in GENDERS)
            raise ValueError(f"Value should be one of the {values}")
        return val


class ClientIDsField(Field):
    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError(f"Client IDs should be a list type, not a {type(value)}")
        if not all(isinstance(cid, int) for cid in value):
            raise ValueError("Client IDs value should be a int type")
        if len(value) == 0:
            raise ValueError("List IDs can not be empty")
        return value


class BaseRequest(object):
    def __new__(cls, *args, **kwargs):
        cls.fields = [k for k, v in cls.__dict__.items() if isinstance(v, Field)]
        return super(BaseRequest, cls).__new__(cls)

    def __init__(self, request: dict, ctx=None, store=None):
        self.context = ctx
        self.store = store
        self.is_admin = request.is_admin
        for field in self.fields:
            setattr(self, field, request.arguments.get(field))


class OnlineScoreRequest(BaseRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def __init__(self, request, ctx=None, store=None):
        super().__init__(request, ctx=ctx, store=store)
        self.context["has"] = [f for f in self.fields if getattr(self, f) is not None]
        if (
            (self.phone is None or self.email is None)
            and (self.gender is None or self.birthday is None)
            and (self.first_name is None or self.last_name is None)
        ):
            raise ValueError(
                """There is at least one pair "phone number or email",
                             "first_name or last_name", "gender or birthday"
                             must be present in arguments"""
            )

    def do(self):
        if self.is_admin:
            return {"score": 42}
        else:
            return {
                "score": get_score(
                    store="",
                    phone=self.phone,
                    email=self.email,
                    birthday=self.birthday,
                    gender=self.gender,
                    first_name=self.first_name,
                    last_name=self.last_name,
                )
            }


class ClientsInterestsRequest(BaseRequest):
    client_ids = ClientIDsField(required=True, nullable=False)
    date = DateField(required=False, nullable=True)

    def __init__(self, request, ctx=None, store=None):
        super().__init__(request, ctx=ctx, store=store)
        if self.client_ids is None:
            raise ValueError("client ID must be present")

    def do(self):
        res = {arg: get_interests(self.store, arg) for arg in self.client_ids}
        self.context["nclients"] = len(res)
        return res


class MethodRequest:
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    def __init__(self, request):
        body = request["body"]
        self.account = body.get("account")
        self.login = body.get("login")
        self.token = body.get("token")
        self.arguments = body.get("arguments")
        self.method = body.get("method")

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN

    def is_authenticated(self):
        if self.is_admin:
            msg = datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        else:
            msg = self.account + self.login + SALT
        digest = hashlib.sha512(msg.encode()).hexdigest()
        return digest == self.token


def method_handler(request, ctx, store):
    request_router = {
        "online_score": OnlineScoreRequest,
        "clients_interests": ClientsInterestsRequest,
    }

    try:
        req = MethodRequest(request)
        logging.debug("Request parsed correctly")
    except ValueError as e:
        return str(e), INVALID_REQUEST

    if not req.is_authenticated():
        return ERRORS[FORBIDDEN], FORBIDDEN

    try:
        method = request_router[req.method](req, ctx, store)
    except KeyError:
        return f"Method {req.method} not found", INVALID_REQUEST
    except ValueError as e:
        return str(e), INVALID_REQUEST
    return method.do(), OK


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = None

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except IOError:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers},
                        context,
                        self.store,
                    )
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {
                "error": response or ERRORS.get(code, "Unknown Error"),
                "code": code,
            }
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode())
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
