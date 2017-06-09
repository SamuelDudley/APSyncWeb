import sys, time, os, errno, re
from pymavlink import mavutil


    
class Connection(object):
    def __init__(self, connection):
        self.control_connection = mavutil.mavlink_connection(connection) # a MAVLink connection
        self.control_link = mavutil.mavlink.MAVLink(self.control_connection)
        self.control_link.srcSystem = 11
        self.control_link.srcComponent = 220
        
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


class TimeoutExpired(Exception):
    pass


def pid_exists(pid):
    """Check whether pid exists in the current process table."""
    if pid < 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError, e:
        return e.errno == errno.EPERM
    else:
        return True

def wait_pid(pid, timeout=None):
    """Wait for process with pid 'pid' to terminate and return its
    exit status code as an integer.

    If pid is not a children of os.getpid() (current process) just
    waits until the process disappears and return None.

    If pid does not exist at all return None immediately.

    Raise TimeoutExpired on timeout expired (if specified).
    """
    def check_timeout(delay):
        if timeout is not None:
            if time.time() >= stop_at:
                raise TimeoutExpired
        time.sleep(delay)
        return min(delay * 2, 0.04)

    if timeout is not None:
        waitcall = lambda: os.waitpid(pid, os.WNOHANG)
        stop_at = time.time() + timeout
    else:
        waitcall = lambda: os.waitpid(pid, 0)

    delay = 0.0001
    while 1:
        try:
            retpid, status = waitcall()
        except OSError, err:
            if err.errno == errno.EINTR:
                delay = check_timeout(delay)
                continue
            elif err.errno == errno.ECHILD:
                # This has two meanings:
                # - pid is not a child of os.getpid() in which case
                #   we keep polling until it's gone
                # - pid never existed in the first place
                # In both cases we'll eventually return None as we
                # can't determine its exit status code.
                while 1:
                    if pid_exists(pid):
                        delay = check_timeout(delay)
                    else:
                        return
            else:
                raise
        else:
            if retpid == 0:
                # WNOHANG was used, pid is still running
                delay = check_timeout(delay)
                continue
            # process exited due to a signal; return the integer of
            # that signal
            if os.WIFSIGNALED(status):
                return os.WTERMSIG(status)
            # process exited using exit(2) system call; return the
            # integer exit(2) system call has been called with
            elif os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
            else:
                # should never happen
                raise RuntimeError("unknown process exit status")



class MatchDict(dict):
    def get_matching(self, event):
        return dict((k, v) for k, v in self.iteritems() if k.split('_')[0] == event)