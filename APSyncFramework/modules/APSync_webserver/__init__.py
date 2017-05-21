import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import time, os, json

from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.json_utils import json_wrap_with_target
from APSyncFramework.utils.file_utils import read_config, write_config

from pymavlink import mavutil

live_web_sockets = set()

class WebserverModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(WebserverModule, self).__init__(in_queue, out_queue, "webserver")
        self.main_counter = 0
        self.mavlink = mavutil.mavlink.MAVLink('')
        
    def process_in_queue_data(self, data):
        websocket_send_message(data)
           
    def send_out_queue_data(self, data):
        self.out_queue.put_nowait(data)
        
        # the following is an example of 'sending' a mavlink msg from
        # a module with no direct mavlink connection
        msg = self.mavlink.heartbeat_encode(
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode = mavutil.mavlink.MAV_MODE_FLAG_TEST_ENABLED,
            custom_mode = 0,
            system_status = 4)
         
        self.out_queue.put_nowait(json_wrap_with_target(msg, target = 'mavlink'))
        
    def main(self):
        if self.main_counter == 0:
            self.main_counter += 1
            main(self)
        else:
            time.sleep(0.1)
    
    def unload(self):
        # override the unload method
        stop_tornado()
        self.needs_unloading.set()
        
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        configs = read_config() # we read the .json config file on every non-websocket http request
        for config_option in configs:
            print "config_option: %s" %str(config_option)         
        self.render("index.html", configs=configs)

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
        # the target needs to be passed from the web interface
        write_config(json.loads(message))
        targeted_message = json_wrap_with_target(message, target = 'mavlink')
        self.callback(targeted_message)

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
    # find config files, relative to where this .py file is kept:
    confdir = os.path.dirname(os.path.realpath(__file__))
    print confdir
    server = tornado.httpserver.HTTPServer(application, ssl_options = {
                                                                       "certfile": os.path.join(confdir,"certs","certificate.pem"),
                                                                       "keyfile": os.path.join(confdir,"certs","privatekey.pem")
                                                                       }
                                           )
    port = int(module.config["webserver_port"])
    server.listen(port)
#     server = application.listen(8888)
    print("Starting Tornado on port {0}".format(port))
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