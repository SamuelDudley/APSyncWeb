
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import Connection
from APSyncFramework.utils.json_utils import json_wrap_with_target

import os, time, select
os.environ['MAVLINK20'] = '1' # force MAVLink v2 for the moment
import pymavlink
from pymavlink import mavutil

class MavlinkModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(MavlinkModule, self).__init__(in_queue, out_queue, "mavlink")
        
        mavutil.set_dialect(self.config['dialect'])
        self.connection_str = self.config['connection']
        self.connection = None
                    
    def main(self):   
        if not self.connection:
            try:
                self.connection = Connection(self.connection_str)
                self.connection.set_system(int(self.config['system_id']))
                self.connection.set_component(int(self.config['component_id']))
            except Exception as err:
                print("Failed to connect to %s : %s" %(self.connection_str,err))
                self.connection = None
                time.sleep(0.1)
        if self.connection:
            self.process_mavlink_connection_in()

    
    def process_in_queue_data(self, data):    
        # check to see if the data is an encoded mavlink message
        if getattr(data, '__module__', None) == mavutil.mavlink.__name__:
            print("{0} module sending MAVLink message {1}".format(self.name, data))
            # send the mavlink message
            # TODO: do we need to re-encode the message to keep the sequence number intact?
            self.connection.control_link.send(data)

        # handle JSON data here e.g. configuration or unload command
        else:
            print("{0} module got the following data: {1}".format(self.name, data))
            pass
        

    def process_mavlink_connection_in(self):
        inputready,outputready,exceptready = select.select([self.connection.control_connection.port],[],[],0.1)
        # block for 0.1 sec if there is nothing on the connection
        # otherwise we just dive right in...
        for s in inputready:
            msg = self.connection.control_connection.recv_msg()
            if msg:
                msg_type = msg.get_type()
                if msg_type == "ATTITUDE":
                    self.out_queue.put_nowait(json_wrap_with_target(msg.to_dict(), target = 'webserver'))
                else:
                    pass
                
def init(in_queue, out_queue):
    '''initialise module'''
    return MavlinkModule(in_queue, out_queue)
    