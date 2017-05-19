#!/usr/bin/python
# when run from this entry point, you don't need to explicity set your PYTHONPATH to have the APSyncFramework/ folder in it.
# 
from APSyncFramework import APSync
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import Connection
from APSyncFramework.utils.json_utils import json_wrap_with_target

apsync_state = None

if __name__ == '__main__':
    from optparse import OptionParser
    
    parser = OptionParser('APSync.py [options]')
    
    parser.add_option("--connection", dest="connection", type='str',
                      help="Flight computer connection", default="tcp:127.0.0.1:5763")
    
    parser.add_option("--debug", dest="debug",
                      help="Enable debug output", default=False, choices=[False,True])
    
    parser.add_option("--heartbeat", dest="heartbeat",
                      help="Send heartbeats from flight computer", default=False, choices=[False,True])
    
    parser.add_option("--ap_sys_id", dest="autopilot_system_id",
                      help="The system ID of the autopilot attached to the flight computer", default=1)
    
    parser.add_option("--dialect", dest="dialect", help="MAVLink dialect", default="ardupilotmega")
    
    optsargs = parser.parse_args()
    (opts,args) = optsargs
    apsync_state = APSync.APSync(optsargs)
    apsync_state.main_loop()

