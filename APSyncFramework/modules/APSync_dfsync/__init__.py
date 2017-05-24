
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import Connection 
from APSyncFramework.utils.json_utils import json_wrap_with_target
from APSyncFramework.utils.file_utils import mkdir_p

import os, time, subprocess, uuid, shutil
from datetime import datetime

class DFSyncModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(DFSyncModule, self).__init__(in_queue, out_queue, "dfsync")
        self.have_path_to_cloud = False
        self.is_not_armed = True#None
        self.datalog_dir = '/home/uas/dataflash-mav/'
        self.datalog_archive_dir = '/home/uas/dflogger/dataflash-archive/'
        self.datalogs = {}
        self.okay_to_sync = {}
        self.old_time = 15 #seconds
        
        self.cloudsync_port = 2221
        
        self.cloudsync_user = 'apsync'
        self.cloudsync_address = 'www.mavcesium.io'
        self.cloudsync_remote_dir = '/home/apsync/mav/'
        self.vehicle_unique_id = uuid.uuid4()

    def main(self):
        current_info = self.stat_files_in_dir(self.datalog_dir)
        new_info = {}
        for key in current_info.keys():
            if key in self.datalogs:
                if (current_info[key]['size'] == self.datalogs[key]['size'] and  current_info[key]['modify'] == self.datalogs[key]['modify']):
                    current_info[key]['age'] = time.time()-self.datalogs[key]['time']
                    current_info[key]['time'] = self.datalogs[key]['time']
                    new_info[key] = current_info[key]
            else:
                current_info[key]['age'] = time.time()-current_info[key]['time']
                new_info[key] = current_info[key]
        # remove away any files we can no longer see
        self.datalogs = dict(new_info)
        
        self.okay_to_sync = {}
        for key in self.datalogs.keys():
            if self.datalogs[key]['age'] > self.old_time:
                self.okay_to_sync[key] = self.datalogs[key]['modify']
        # we have a dict of file names and agessorted(data.items(), key=)
        self.okay_to_sync = sorted(self.okay_to_sync.items(), key=lambda x:x[1])
        print self.okay_to_sync
        
        if (len(self.okay_to_sync) == 0): #self.is_not_armed or self.needs_unloading
            time.sleep(2)
            return
            
        
        # sync the oldest file first
        file_to_send = self.okay_to_sync[-1][0]
        send_path = os.path.join(self.datalog_dir,file_to_send)

        new_folder = 'dataflash-{0}-{1}'.format(self.vehicle_unique_id, datetime.utcnow().strftime('%Y%m%d%H%M%S'))
        rsynccmd = """rsync -aHzv -h --progress --stats -e "ssh -p {0}" "{1}" {2}@{3}:{4}""".format(self.cloudsync_port,
                                                                                                  send_path, self.cloudsync_user,
                                                                                                  self.cloudsync_address,
                                                                                                  self.cloudsync_remote_dir
                                                                                                  )
        print rsynccmd
        rsyncproc = subprocess.Popen(rsynccmd,
                                     shell=True,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                    )                  
        curr = ''
        while (self.is_not_armed): # unlod, path to cloud
            next_line = rsyncproc.stdout.read(10).decode("utf-8")
            curr += next_line
            bits = curr.split('\r')
            if len(bits) > 1:
                current_status = bits[-2].strip().split()
                if len(current_status) == 4:
                    current_status.append(str(time.time()))
                    current_status.append(file_to_send)
                    # send this to the webserver...
                    print dict(zip(['data_sent', 'percent_sent', 'sending_rate', 'time_remaining', 'current_time', 'file'], current_status))
                curr = bits[-1]
            if not next_line:
                break
            
        # wait until process is really terminated
        
        exitcode = rsyncproc.wait()
        # check exit code
        if exitcode==0:
            target_path = os.path.join(self.datalog_archive_dir, new_folder)
            mkdir_p(target_path)
            shutil.move(send_path, os.path.join(target_path, file_to_send))
            print 'done!'
        else:
            print"WARNING: looks like some error occured :("
        
    
    def stat_files_in_dir(self, datalog_dir):
        ret = {}
        datalogs = [f for f in os.listdir(datalog_dir) if os.path.isfile(os.path.join(datalog_dir, f))]
        for datalog in datalogs:
            datalog_path = os.path.join(datalog_dir, datalog)
            datalog_stat = os.stat(datalog_path)
            ret[datalog] = {'size':datalog_stat.st_size, 'modify':datalog_stat.st_mtime, 'time':time.time()}
        return ret

        
    def process_in_queue_data(self, data):    
        print("{0} module got the following data: {1}".format(self.name, data))
        # look at mavlink and make sure we are not armed..
        # look at network and make sure we have a path to internet
        pass
     
def init(in_queue, out_queue):
    '''initialise module'''
    return DFSyncModule(in_queue, out_queue)
    