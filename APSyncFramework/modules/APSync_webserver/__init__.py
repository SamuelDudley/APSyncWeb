import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import time, os, json

from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.json_utils import json_wrap_with_target
from APSyncFramework.utils.file_utils import read_config, write_config,file_get_contents
from APSyncFramework.utils.network_utils import make_ssh_key

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
        print "callback routed to send_out_queue_data for queue-up:"+str(data)
        # work out what the data is and either pass it to a specific module for mandling, or handle it here immediately. 
        
        # this is passing the data off to the "mavlink" module to handle this, as we don't know how to do that.
        if "mavlink_data" in data.keys():
            if "mavpackettype" in data["mavlink_data"].keys():
                msg_type = data["mavlink_data"]["mavpackettype"]
            else:
                # mavlink_data requires mavpackettype
                return
            
            if msg_type == 'HEARTBEAT':
                # the following is an example of 'sending' a mavlink msg from
                # a module with no direct mavlink connection
                msg = self.mavlink.heartbeat_encode(
                mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                base_mode = mavutil.mavlink.MAV_MODE_FLAG_TEST_ENABLED,
                custom_mode = 0,
                system_status = 4)
            self.out_queue.put_nowait(json_wrap_with_target(msg, target = 'mavlink'))
            
        # if its a block of config-file type data, we'll just write it to disk now.       
        elif "config" in data.keys():
            config = data["config"]
            write_config(config)
            
        # if it's something else calling itself json_data, then we will handle it here and pretend it came from somwhere else
        elif "json_data" in data.keys(): # 
            make_ssh_key()
            folder = os.path.join(os.path.expanduser('~'), '.ssh')

            cred = json.loads(file_get_contents(folder+"/id_apsync"))
            j = '{"json_data":{"result":"'+cred+'","replyto":"getIdentityResponse"}}';
            msg = json.loads(j)
            # send it back out the websocket immediately, no need to wrap it, as it's not being routed beyond tornado and browser. 
            websocket_send_message(msg)
        
        else:
            pass
        
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
        print("received websocket message: {0}".format(message))
        message = json.loads(message)
        self.callback(message) # this sends it to the module.send_out_queue_data for further processing.

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