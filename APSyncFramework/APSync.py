import time, select, sys, signal, os
import multiprocessing, threading, setproctitle
import traceback
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import PeriodicEvent
from APSyncFramework.utils.json_utils import json_unwrap_with_target

# global for signals only.
apsync_state = []

#class APSyncSettings(object):
#    def __init__(self):
#        # see mavproxy
#        pass

class APSync(object):
    def __init__(self, optsargs):
        self.modules = []
        self.should_exit = False
        self.optsargs = optsargs
    
    @property
    def loaded_modules(self):
        return [module_instance.name for (module_instance,module) in self.modules]
#         self.settings = APSyncSettings(
#             [
#              ]

    def clear_zipimport_cache(self):
        """Clear out cached entries from _zip_directory_cache.
        See http://www.digi.com/wiki/developer/index.php/Error_messages"""
        import sys, zipimport
        syspath_backup = list(sys.path)
        zipimport._zip_directory_cache.clear()
    
        # load back items onto sys.path
        sys.path = syspath_backup
        # add this too: see https://mail.python.org/pipermail/python-list/2005-May/353229.html
        sys.path_importer_cache.clear()
    
    # http://stackoverflow.com/questions/211100/pythons-import-doesnt-work-as-expected
    # has info on why this is necessary.
    
    def import_package(self,name):
        """Given a package name like 'foo.bar.quux', imports the package
        and returns the desired module."""
        import zipimport
        try:
            mod = __import__(name)
        except ImportError:
            self.clear_zipimport_cache()
            mod = __import__(name)
    
        components = name.split('.')
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    
    def load_module(self, modname, quiet=False, start_now=True):
        '''load a module'''
        modpaths = ['APSyncFramework.modules.APSync_%s' % modname, modname]    
        if modname in self.loaded_modules:
            if not quiet:
                print("module %s already loaded" % modname)
            return False
        for modpath in modpaths:
            try:
                m = self.import_package(modpath)
                reload(m)
                in_queue = multiprocessing.Queue()
                out_queue = multiprocessing.Queue()
                m_instance = m.init(in_queue, out_queue)
                if isinstance(m_instance, APSync_module.APModule):
                    self.modules.append((m_instance,m))
                    if not quiet:
                        print("Loaded module %s" % (modname,))
                    
                    if start_now:
                        m_instance.start()
    
                    return True
                else:
                    ex = "%s.init did not return a APModule instance" % modname
                    break
            except ImportError as msg:
                ex = msg
        
        print("Failed to load module: {0} {1}".format(ex, traceback.format_exc()))
        return False
    
    def unload_module(self,modname,apsync_state=[]):
        '''unload a module'''
        if modname in self.loaded_modules:
            where = (idx for idx,(i,m) in enumerate(self.modules) if i.name==modname).next()
            (i,m) = self.modules[where]
            if hasattr(i, 'unload'):
                i.unload()
            del self.modules[where]
            print("Unloaded module %s" % modname)
            return True
        print("Unable to find module %s" % modname)
        return False
    
    def check_pings(self):
        pass
    
    def main_loop(self):
        '''main processing loop'''
        
        pid = os.getpid()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.load_module('mavlink', start_now=True)
        self.load_module('webserver', start_now=True)
        lock = threading.Lock()
        t = threading.Thread(target=self.queue_handling, args = (lock, apsync_state,))
        t.daemon = True
        t.start()
        periodic_events = []
        periodic_events.append(PeriodicEvent(frequency = 1, event = self.check_pings))
        while not self.should_exit:
            time.sleep(0.1)
        self.should_exit = True
        t.join()
    
    def queue_handling(self,lock, apsync_state):
        setproctitle.setproctitle("APSync")
        modules = self.modules
        module_names = self.loaded_modules
        out_queues = [i.out_queue for (i,m) in self.modules]
        in_queues = [i.in_queue for (i,m) in self.modules]
        queue_file_discriptors = [q._reader for q in out_queues]
        
        start = time.time()
        count = 0
        
        while not self.should_exit:
            (inputready,outputready,exceptready) = select.select(queue_file_discriptors,[],[],0.1)
            for q in out_queues:
                while not q.empty():
                # drain the queue
                    obj = q.get_nowait()
                    try:
                        (target,data,priority) = json_unwrap_with_target(obj)
                    except ValueError:
                        # did not get enough values to unpack
                        # move on to the next obj
                        continue
                    try:
                        idx = module_names.index(target)
    #                     print target
                        in_queues[idx].put(data)
                    except ValueError:
                        # could not find the target
                        # move on to the next obj
                        continue
    #         if time.time()-start > 10:
    #             if count == 0:
    #                 self.unload_module('webserver')
    #                 count+=1
                
    def signal_handler(self,signum, frame):
        '''callback for CTRL-C'''
        for modname in self.loaded_modules: 
            self.unload_module(modname)
        self.should_exit = True
        sys.exit(0)
    
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
    apsync = APSync.APSync(optsargs)
    apsync.main_loop()
    