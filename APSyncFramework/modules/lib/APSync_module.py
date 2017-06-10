# A template for APSync process based modules
from multiprocessing import Process, Event
import threading
import time
import signal, select
import traceback
import setproctitle
from APSyncFramework.utils.common_utils import PeriodicEvent
from APSyncFramework.utils.json_utils import ping, json_wrap_with_target
from APSyncFramework.utils.file_utils import read_config, write_config

class APModule(Process):
    '''The base class for all modules'''
    def __init__(self, in_queue, out_queue, name, description = None):
        super(APModule, self).__init__()
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.daemon = True
        self.config_list= [] # overwrite this list
        self.config_changed = False
        self.config = read_config()
        self.start_time = time.time()
        self.last_ping = None
        self.needs_unloading = Event()
        self.lock = threading.Lock()
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.name = name
        self.ping = PeriodicEvent(frequency = 1.0/3.0, event = self.send_ping)
        self.in_queue_thread = threading.Thread(target=self.in_queue_handling,
                                                args = (self.lock,))
        self.in_queue_thread.daemon = True
        setproctitle.setproctitle(self.name)

        if description is None:
            self.description = "APSync {0} process".format(self.name)
        else:
            self.description = description
    
    def update_config(self, config_list = []):
        if len(config_list):
            self.config_list = config_list
        for (var_name, var_default) in self.config_list:
            self.set_config(var_name, var_default)
            
        if self.config_changed:
            # TODO: send a msg to the webserver to update / reload the current page
            self.log('At least one of your cloudsync settings was missing or has been updated, please reload the webpage if open.', 'INFO')
            self.config_changed = False
            
        config_on_disk = read_config()
        for k in config_on_disk.keys():
            if not k in self.config:
                self.config[k] = config_on_disk[k]
        
        write_config(self.config)
    
    def send_ping(self):
        self.out_queue.put_nowait(ping(self.name, self.pid))
            
    def exit_gracefully(self, signum, frame):
        self.unload()
    
    def unload(self):
        print self.name, 'called unload'
        self.unload_callback()
        self.needs_unloading.set()
        
    def unload_callback(self):
        ''' overload to perform any module specific cleanup'''
        pass
        
    def run(self):
        if self.in_queue_thread is not None:
            self.in_queue_thread.start()
        while not self.needs_unloading.is_set():
            try:
                self.main()
            except:
                print ("FATAL: module ({0}) exited while multiprocessing".format(self.name)) 
                traceback.print_exc()
                # TODO: logging here
        print self.name, 'main finished'
    
    def main(self):
        pass
    
    def in_queue_handling(self, lock=None):
        while not self.needs_unloading.is_set():
            (inputready,outputready,exceptready) = select.select([self.in_queue._reader],[],[],0.1)
            for s in inputready:
                while not self.in_queue.empty():
                # drain the queue
                    data = self.in_queue.get_nowait()
                    if isinstance(data, Unload):
                        self.unload()
                    else:
                        # do something useful with the data...
                        self.process_in_queue_data(data)
            self.ping.trigger()
        
        print self.name, 'in queue finished'

    def process_in_queue_data(self, data):
        pass
    
    def log(self, message, level = 'INFO'):
        
#         CRITICAL
#         ERROR
#         WARNING
#         INFO
#         DEBUG
#         NOTSET
        self.out_queue.put_nowait(json_wrap_with_target({'msg':message, 'level':level}, target = 'logging'))
    
    def set_config(self, var_name, var_default):
        new_val = self.config.get(var_name, var_default)
        try:
            cur_val = self.config[var_name]
            if new_val != cur_val:
                self.config_changed = True
        except:
            self.config_changed = True
        
        finally:
            self.config[var_name] = new_val
            return new_val
        
class Unload():
    def __init__(self, name):
        self.ack = False
        