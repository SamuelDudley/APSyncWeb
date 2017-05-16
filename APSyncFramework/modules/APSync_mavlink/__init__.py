
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import Connection
from APSyncFramework.utils.json_utils import json_wrap_with_target

import os, time, select
os.environ['MAVLINK20'] = '1' # force MAVLink v2 for the moment
from pymavlink import mavutil

class MavlinkModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(MavlinkModule, self).__init__(in_queue, out_queue, "mavlink")
        mavutil.set_dialect("ardupilotmega")
        self.connection_str = 'tcp:127.0.0.1:5763'
        self.connection = None
            
    def main(self):        
        if not self.connection:
            try:
                self.connection = Connection(self.connection_str)
            except Exception as err:
                print("Failed to connect to %s : %s" %(self.connection_str,err))
                self.connection = None
                time.sleep(0.1)
        if self.connection:
            self.process_mavlink_connection_in()
    
    def process_in_queue_data(self, data):
        print self.name, 'got', data

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
        
def init(in_queue, out_queue):
    '''initialise module'''
    return MavlinkModule(in_queue, out_queue)
    