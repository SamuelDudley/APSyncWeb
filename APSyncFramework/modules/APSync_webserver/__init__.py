import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver

import time, os

from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.json_utils import json_wrap_with_target

# TODO unload is to come over the in queue

live_web_sockets = set()

class WebserverModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(WebserverModule, self).__init__(in_queue, out_queue, "webserver")
        self.main_counter = 0   
            
    def process_in_queue_data(self, data):
        websocket_send_message(data)
           
    def send_out_queue_data(self, data):
        self.out_queue.put_nowait(json_wrap_with_target(data, target = 'mavlink'))
        
    def main(self):
        if self.main_counter == 0:
            self.main_counter += 1
            main(self)
        else:
            time.sleep(0.1)
    
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", messages="")

class DefaultWebSocket(tornado.websocket.WebSocketHandler):
    def initialize(self, callback):
        self.callback = callback
        
    def open(self):
        print("websocket opened!")
        self.set_nodelay(True)
        live_web_sockets.add(self)
        self.write_message('you have been connected!')
     
    def on_message(self, message):
        print("incoming message", message)
        self.callback(message)
         
    def on_close(self):
        print("websocket closed")
        
class Application(tornado.web.Application):
    def __init__(self, module):
        handlers = [
            (r"/", MainHandler),
            (r"/websocket/", DefaultWebSocket, dict(callback=module.send_out_queue_data)),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        super(Application, self).__init__(handlers, **settings)

def start_app(module):
    application = Application(module)
    server = tornado.httpserver.HTTPServer(application, ssl_options = {
                                                                       "certfile": os.path.join("certs/certificate.pem"),
                                                                       "keyfile": os.path.join("certs/privatekey.pem")
                                                                       }
                                           )
    server.listen(4443)
#     server = application.listen(8888)
    print "Starting app"
    return server

def close_all_websockets():
    removable = set()
    for ws in live_web_sockets:
        removable.add(ws)
    for ws in removable:
        live_web_sockets.remove(ws)
            
def stop_tornado():
    close_all_websockets()
    ioloop = tornado.ioloop.IOLoop.current()
    ioloop.add_callback(ioloop.stop)
    print "Asked Tornado to exit"

def websocket_send_message(message):
    removable = set()
    for ws in live_web_sockets:
        if not ws.ws_connection or not ws.ws_connection.stream.socket:
            removable.add(ws)
        else:
            ws.write_message(message)
    for ws in removable:
        live_web_sockets.remove(ws)

def main(module):
    server = start_app(module=module)
    tornado.ioloop.IOLoop.current().start()
    print "Tornado finished"
    server.stop()

def init(in_queue, out_queue):
    '''initialise module'''
    return WebserverModule(in_queue, out_queue)