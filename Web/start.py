import tornado.ioloop
import tornado.httpserver
import tornado.options
import tornado.web
import json
import os
import subprocess
import datetime

class TestButton(tornado.web.RequestHandler):
        def post(self):
                data = json.loads(self.request.body.decode('utf-8'))
                host = str(data[0]["value"])
                nrping = str(data[1]["value"])
                comand = "ping -c " + nrping + " " + host
                result = subprocess.call(['ping','-c',nrping,host])
                now = str(datetime.datetime.now())
                if result == 0 :
                        ping_response = {'time': now , 'result':"Server up"}
                else :
                        ping_response = {'time': now , 'result':"Server down"}
                self.write(json.dumps(ping_response))

class HomePage(tornado.web.RequestHandler):
        def get(self):
                self.render('index.html')

application= tornado.web.Application([
        (r"/CSS/(.*)", tornado.web.StaticFileHandler, {'path': "/tornado/CSS"}),
        (r"/", HomePage),
        (r"/ping", TestButton),

])
