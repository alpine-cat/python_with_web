# -*- coding: utf-8 -*-
"""
    shortly
    ~~~~~~~

    A simple URL shortener using Werkzeug and redis.

    :copyright: 2007 Pallets
    :license: BSD-3-Clause
"""
import os

import redis

from db import get_url, insert_url, get_count, increment_url, get_list_urls
from utils import get_hostname, is_valid_url

from jinja2 import Environment
from jinja2 import FileSystemLoader
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound

from werkzeug.routing import Map
from werkzeug.routing import Rule
from werkzeug.utils import redirect
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response


class Shortly(object):
    def __init__(self, config):
        self.redis = redis.Redis(config["redis_host"], config["redis_port"])
        template_path = os.path.join(os.path.dirname(__file__), "templates")
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_path), autoescape=True
        )
        self.jinja_env.filters["hostname"] = get_hostname
        self.url_map = Map(
            [
                Rule("/", endpoint="home"),
                Rule('/<short_id>', endpoint="follow_short_link"),
                Rule('/create', endpoint="new_url"),
                Rule('/<short_id>_details', endpoint="short_link_details"),
                Rule('/list', endpoint='list_url'),
            ]
        )

    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype="text/html")

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, "on_" + endpoint)(request, **values)
        except NotFound:
            return self.error_404()
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        auth = request.authorization
        if not auth or not self.check_auth(auth.username, auth.password):
            response = self.auth_required(request)
        else:
            response = self.dispatch_request(request)
        return response(environ, start_response)

    def on_home(self, request):
        return self.render_template("homepage.html")

    def on_new_url(self, request):
        error = None
        url = ""
        if request.method == "POST":
            url = request.form['url']
            if not is_valid_url(url):
                error = 'invalid url'
            else:
                id = insert_url(self.redis, url)
                if type(id) == bytes:
                    return redirect('%s_details' % id.decode('utf-8'))
                return redirect('/%s_details' % id)
        return self.render_template("new_url.html", error=error, url=url)

    def on_follow_short_link(self, request, short_id):
        link_target = get_url(self.redis, short_id)
        if not link_target:
            return NotFound()
        increment_url(self.redis, short_id)
        return redirect(link_target)

    def on_short_link_details(self, request, short_id):
        url = get_url(self.redis, short_id)
        if not url:
            return NotFound()
        click_count = get_count(self.redis, short_id)
        link_target = "/"
        return self.render_template(
            "short_link_details.html",
            link_target=link_target,
            short_id=short_id,
            click_count=click_count,
        )

    def on_list_url(self, request):
        error = None
        list_urls = get_list_urls(self.redis)
        if not list_urls:
            error = "no urls found"
        return self.render_template("list_url.html", error=error, url_list=list_urls)

    def check_auth(self, username, password):
        return username == 'admin' and password == 'admin'

    def auth_required(self, request):
        return Response(
            "Please log-in to continue",
            401,
            {"WWW-Authenticate": 'Basic realm="login required"'}
        )

    def error_404(self):
        response = self.render_template("404.html")
        response.status_code = 404
        return response

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)
