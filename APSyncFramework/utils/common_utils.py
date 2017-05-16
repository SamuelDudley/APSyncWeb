# http://chimera.labs.oreilly.com/books/1230000000393/ch12.html#_polling_multiple_thread_queues
import queue
import socket
import os
import sys, time
from pymavlink import mavutil

class PollableQueue(queue.Queue,object):
    def __init__(self):
        super(PollableQueue, self).__init__()
        # Create a pair of connected sockets
        if os.name == 'posix':
            self._putsocket, self._getsocket = socket.socketpair()
        else:
            # Compatibility on non-POSIX systems
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            self._putsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._putsocket.connect(server.getsockname())
            self._getsocket, _ = server.accept()
            server.close()

    def fileno(self):
        return self._getsocket.fileno()

    def put(self, item):
        super(PollableQueue, self).put(item)
        self._putsocket.send(b'x')

    def get(self):
        self._getsocket.recv(1)
        return super(PollableQueue, self).get()
    
class Connection(object):
    def __init__(self, connection):
        self.control_connection = mavutil.mavlink_connection(connection) # a MAVLink connection
        self.control_link = mavutil.mavlink.MAVLink(self.control_connection)
        self.control_link.srcSystem = 11
        self.control_link.srcComponent = 220 #195
        
    def set_component(self, val):
        self.control_link.srcComponent = val
    
    def set_system(self, val):
        self.control_link.srcSystem = val
        
class PeriodicEvent(object):
    '''a class for fixed frequency events'''
    def __init__(self, frequency, clock = None, event = None):
        if clock is None:
            self.wall_time = True
        else:
            self.wall_time = False
        
        self.frequency = float(frequency)
        self.event = event
        if self.wall_time:
            self.last_time = time.time()
        else:
            self.last_time = clock

    def force(self):
        '''force immediate triggering'''
        self.last_time = 0
        
    def trigger(self, clock = None):
        '''return True if we should trigger now'''
        if self.wall_time:
            tnow = time.time()
        else:
            if clock is not None:
                tnow = clock
            else:
                print('Error: Clock init was not wall time, supply clock value with .trigger(clock=)')
                sys.exit(1)
        if self.frequency == 0:
            return False
        
        if tnow < self.last_time:
            if self.wall_time:
                print("Warning, time moved backwards. Restarting timer.")
            self.last_time = tnow

        if self.last_time + (1.0/self.frequency) <= tnow:
            self.last_time = tnow
            if self.event:
                self.event()
            return True
        return False
    
# below here is a basic test suite for the PollableQueue 
if __name__ == '__main__':
    import select
    import threading
    import time
    
    def consumer(queues):
        '''
        Consumer that reads data on multiple queues simultaneously
        '''
        while True:
            can_read, _, _ = select.select(queues,[],[])
            for r in can_read:
                item = r.get()
                print('Got:', item)
    
    q1 = PollableQueue()
    q2 = PollableQueue()
    q3 = PollableQueue()
    t = threading.Thread(target=consumer, args=([q1,q2,q3],))
    t.daemon = True
    t.start()
    
    # Feed data to the queues
    while True:
        q1.put(1)
        q2.put(10)
        q3.put('hello')
        q2.put(15)
        time.sleep(0.01)
    
    time.sleep(1)

