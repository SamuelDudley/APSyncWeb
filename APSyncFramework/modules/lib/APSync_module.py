# A template for APSync process based modules
from multiprocessing import Process
import multiprocessing
import threading
import os
import signal, select
import traceback

import setproctitle

class APModule(Process):
    '''The base class for all modules'''

    def __init__(self, in_queue, out_queue, name, description = None):
        super(APModule, self).__init__()
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.daemon = True
        self.needs_unloading = multiprocessing.Event()
        self.lock = threading.Lock()
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.name = name
        self.in_queue_thread = threading.Thread(target=self.in_queue_handling,
                                                args = (self.lock,))
        self.in_queue_thread.daemon = True

        
        setproctitle.setproctitle(self.name)

        if description is None:
            self.description = "APSync" + name + " process"
        else:
            self.description = description
            
    def exit_gracefully(self, signum, frame):
        self.unload()
    
    def unload(self):
        self.needs_unloading.set()
        
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
    
    def main(self):
        pass
    
    def in_queue_handling(self, lock=None):
        while not self.needs_unloading.is_set():
            (inputready,outputready,exceptready) = select.select([self.in_queue._reader],[],[],0.1)
            for s in inputready:
                while not self.in_queue.empty():
                # drain the queue
                    data = self.in_queue.get_nowait()
                    # do something useful with the data...
                    self.process_in_queue_data(data)

    
    def process_in_queue_data(self, data):
#         print('{0} got {1}'.format(self.name, data))
        pass