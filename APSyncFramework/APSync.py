import time, select, sys, signal, os, shlex
import multiprocessing, threading, setproctitle
import traceback
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import PeriodicEvent, pid_exists, wait_pid
from APSyncFramework.utils.json_utils import json_unwrap_with_target

# global for signals only.
apsync_state = []

class APSync(object):
    def __init__(self, optsargs):
        self.modules = []
        self.should_exit = False
        self.optsargs = optsargs
    
    @property
    def loaded_modules(self):
        return [module_instance.name for (module_instance,module) in self.modules]

    def clear_zipimport_cache(self):
        '''Clear out cached entries from _zip_directory_cache.
        See http://www.digi.com/wiki/developer/index.php/Error_messages'''
        import zipimport
        syspath_backup = list(sys.path)
        zipimport._zip_directory_cache.clear()
    
        # load back items onto sys.path
        sys.path = syspath_backup
        # add this too: see https://mail.python.org/pipermail/python-list/2005-May/353229.html
        sys.path_importer_cache.clear()
    
    # http://stackoverflow.com/questions/211100/pythons-import-doesnt-work-as-expected
    # has info on why this is necessary.
    
    def import_package(self,name):
        '''Given a package name like 'foo.bar.quux', imports the package
        and returns the desired module.'''
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
                    
                    self.event.set()
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
            pid = i.pid
            i.in_queue.put_nowait(APSync_module.Unload(modname))
            try:
                wait_pid(pid, timeout=0.1)
                timeout = False
            except:
                timeout = True
            
            if timeout and pid_exists(pid):
                os.kill(pid, signal.SIGTERM)
                try:
                    wait_pid(pid, timeout=0.1)
                    timeout = False
                except:
                    timeout = True
            
            if timeout and pid_exists(pid):
                os.kill(pid, signal.SIGKILL)
                try:
                    wait_pid(pid, timeout=0.1)
                    timeout = False
                except:
                    timeout = True
                    
            if timeout and pid_exists(pid):
                print("Failed to kill process with PID: {0}".format(pid))
            del self.modules[where]
            self.event.set()
            print("Unloaded module %s" % modname)
            return True
        print("Unable to find module %s" % modname)
        return False
    
    def reload_module(self, modname):
        pmodule = None
        for (i,m) in self.modules:
            if i.name == modname:
                pmodule = m
        if pmodule is None:
            print("Module %s not loaded" % modname)
            return
        if self.unload_module(modname):
            try:
                reload(pmodule)
            except ImportError:
                self.clear_zipimport_cache()
                reload(pmodule)
            if self.load_module(modname, quiet=True, start_now=True):
                print("Reloaded module %s" % modname)
                return
            
    def check_pings(self):
        for (i,m) in self.modules:
            last_ping = i.last_ping
            if last_ping:
                if time.time()-last_ping['time'] > 10:
                    print('Ping timeout, attempting reload of module {0}'.format(i.name))
                    self.reload_module(i.name)
    
    def main_loop(self):
        '''main processing loop'''
        lock = threading.Lock()
        self.event = threading.Event()
        pid = os.getpid()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.load_module('mavlink', start_now=True)
        self.load_module('webserver', start_now=True)
        
        # TODO: make the input thread optional (this can be replaced by the web UI)
        self.input_loop_queue = multiprocessing.Queue()
        
        input_loop_thread = threading.Thread(target=self.input_loop, args = (lock, apsync_state, self.input_loop_queue))
        input_loop_thread.daemon = True
        input_loop_thread.start()
        
        queue_handling_thread = threading.Thread(target=self.queue_handling, args = (lock, self.event, apsync_state,))
        queue_handling_thread.daemon = True
        queue_handling_thread.start()
        
        periodic_events = []
        periodic_events.append(PeriodicEvent(frequency = 1, event = self.check_pings))
        while not self.should_exit:
            while not self.input_loop_queue.empty():
                # drain the queue
                line = self.input_loop_queue.get_nowait()
                args = self.shlex_quotes(line.lower())
                cmd = args[0]
                if cmd == 'module':
                    self.cmd_module(args[1:])
            for event in periodic_events:
                event.trigger()
                
            time.sleep(0.1)
        self.should_exit = True
        queue_handling_thread.join()
        
    def input_loop(self, lock, apsync_state, out_queue):
        '''wait for user input'''
        while not self.should_exit:
            line = None
            try:
                if not self.should_exit:
                    line = raw_input("APSync >> ")
            except EOFError:
                self.should_exit = True
            if line:
                line = line.strip() # remove leading and trailing whitespace
                out_queue.put_nowait(line)
    
    def queue_handling(self, lock, event, apsync_state):
        setproctitle.setproctitle("APSync")

        while not self.should_exit:
            if event.is_set():
                modules = self.modules
                module_names = self.loaded_modules
                out_queues = [i.out_queue for (i,m) in modules]
                in_queues = [i.in_queue for (i,m) in modules]
                queue_file_discriptors = [q._reader for q in out_queues]
                event.clear()

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
                        if target == 'watchtasks':
                            where = (idx for idx,(i,m) in enumerate(self.modules) if i.name==data['name']).next()
                            (i,m) = self.modules[where]
                            i.last_ping = data
                        else:
                            idx = module_names.index(target)
                            in_queues[idx].put(data)
                    except ValueError:
                        # could not find the target
                        # move on to the next obj
                        continue
                
    def signal_handler(self,signum, frame):
        '''callback for CTRL-C'''
        for modname in self.loaded_modules: 
            self.unload_module(modname)
        self.should_exit = True
        # TODO: join threads and processes here prior to exit?
        sys.exit(0)
        
    def shlex_quotes(self, value):
        '''see http://stackoverflow.com/questions/6868382/python-shlex-split-ignore-single-quotes'''
        lex = shlex.shlex(value)
        lex.quotes = '"'
        lex.whitespace_split = True
        lex.commenters = ''
        return list(lex)
        
    def cmd_module(self, args):
        '''module commands'''
        usage = "usage: module <list|load|reload|unload>"
        if len(args) < 1:
            print(usage)
            return
        if args[0] == "list":
            print("")
            for (i,m) in self.modules:
                print("\t{0}: {1}".format(i.name, i.description))
        elif args[0] == "load":
            if len(args) < 2:
                print("usage: module load <name>")
                return
            self.load_module(args[1])
        elif args[0] == "reload":
            if len(args) < 2:
                print("usage: module reload <name>")
                return
            modname = args[1]
            self.reload_module(modname)
        elif args[0] == "unload":
            if len(args) < 2:
                print("usage: module unload <name>")
                return
            modname = os.path.basename(args[1])
            self.unload_module(modname)
        else:
            print(usage)
    
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
    
    parser.add_option("--cc_sys_id", dest="companion_system_id",
                      help="The system ID of the companion computer", default=1)
    
    optsargs = parser.parse_args()
    apsync = APSync(optsargs)
    apsync.main_loop()
    
