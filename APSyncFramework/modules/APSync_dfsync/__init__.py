
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import pid_exists, wait_pid
from APSyncFramework.utils.json_utils import json_wrap_with_target
from APSyncFramework.utils.file_utils import mkdir_p

import os, time, subprocess, uuid, shutil, signal, re
from datetime import datetime

class DFSyncModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(DFSyncModule, self).__init__(in_queue, out_queue, "dfsync")
        self.have_path_to_cloud = True#False
        self.is_not_armed = True#None
        self.syncing_enabled = True
        
        self.cloudsync_port = 2221
        self.cloudsync_user = 'apsync'
        self.cloudsync_address = 'www.mavcesium.io'
        self.cloudsync_remote_dir = '/home/apsync/mav/'
        self.datalog_dir = '/home/uas/dataflash-mav/'
        self.datalog_archive_dir = '/home/uas/dflogger/dataflash-archive/'
        self.vehicle_unique_id = uuid.uuid4()
        
        self.datalogs = {}
        self.old_time = 3 #seconds
        self.rsync_time = re.compile(r'[0-9]:([0-5][0-9]):([0-5][0-9])')

    def main(self):
        stat_file_info = self.stat_files_in_dir(self.datalog_dir)
        for key in stat_file_info.keys():
            if key in self.datalogs:
                if (stat_file_info[key]['size'] == self.datalogs[key]['size'] and stat_file_info[key]['modify'] == self.datalogs[key]['modify']):
                    stat_file_info[key]['age'] = time.time()-self.datalogs[key]['time']
                    stat_file_info[key]['time'] = self.datalogs[key]['time']
                    self.datalogs[key] = stat_file_info[key]
            else:
                stat_file_info[key]['age'] = time.time()-stat_file_info[key]['time']
                self.datalogs[key] = stat_file_info[key]
        
        self.files_to_sync = {}
        for key in self.datalogs.keys():
            if self.datalogs[key]['age'] > self.old_time:
                self.files_to_sync[key] = self.datalogs[key]['modify']
        # we have a dict of file names and last modified times
        self.files_to_sync = sorted(self.files_to_sync.items(), key=lambda x:x[1])
        
        if (len(self.files_to_sync) == 0 or not self.okay_to_sync()):
            time.sleep(2)
            return
        
        # sync the oldest file first
        file_to_send = self.files_to_sync[-1][0]
        send_path = os.path.join(self.datalog_dir,file_to_send)

        archive_folder = 'dataflash-{0}-{1}'.format(self.vehicle_unique_id, datetime.utcnow().strftime('%Y%m%d%H%M%S'))
        rsynccmd = """rsync -aHzv -h --progress -e "ssh -p {0}" "{1}" {2}@{3}:{4}""".format(self.cloudsync_port,
                                                                                                  send_path, self.cloudsync_user,
                                                                                                  self.cloudsync_address,
                                                                                                  self.cloudsync_remote_dir
                                                                                                  )
        self.datalogs.pop(file_to_send)
        
        rsyncproc = subprocess.Popen(rsynccmd,
                                     shell=True,
                                     stdin=None,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True,
                                    )                  

        while self.okay_to_sync():
            next_line = rsyncproc.stdout.readline().decode("utf-8")
            if self.rsync_time.search(next_line):
                # we found a line containing a status update
                current_status = next_line.strip().split()
                current_status=current_status[:4]
                current_status.append(str(time.time()))
                current_status.append(file_to_send)
                # send this to the webserver...
                status_update = dict(zip(['data_sent', 'percent_sent', 'sending_rate', 'time_remaining', 'current_time', 'file'], current_status))
                self.out_queue.put_nowait(json_wrap_with_target({'dfsync:sync_update' : status_update}, target = 'webserver'))
                print {'dfsync:sync_update': status_update}
            if not next_line:
                break
        
        if self.okay_to_sync():
            # wait until process is really terminated
            exitcode = rsyncproc.wait()
            # check exit code
            if exitcode == 0:
                # archive the log on the CC
                target_path = os.path.join(self.datalog_archive_dir, archive_folder)
                mkdir_p(target_path)
                shutil.move(send_path, os.path.join(target_path, file_to_send))
                print('INFO: datalog rsync complete for {0}'.format(file_to_send))
            else:
                print('WARNING: an error during datalog rsync for {0}, exit code: {1}'.format(file_to_send, exitcode))
        else:
            # the rsync process is required to exit
            print('INFO: attempting to stop rsync process')
            pid = rsyncproc.pid
            if pid_exists(pid):
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
                print("ERROR: failed to terminate and kill rsync process with pid: {0}".format(pid))
                
            else:
                print('INFO: rsync process stopped successfully')
        
    
    def stat_files_in_dir(self, datalog_dir):
        ret = {}
        datalogs = [f for f in os.listdir(datalog_dir) if os.path.isfile(os.path.join(datalog_dir, f))]
        for datalog in datalogs:
            datalog_path = os.path.join(datalog_dir, datalog)
            datalog_stat = os.stat(datalog_path)
            ret[datalog] = {'size':datalog_stat.st_size, 'modify':datalog_stat.st_mtime, 'time':time.time()}
        return ret

    def okay_to_sync(self):
        if (self.is_not_armed and self.have_path_to_cloud and self.syncing_enabled and not self.needs_unloading.is_set()):
            return True
        else:
            return False
    
    def process_in_queue_data(self, data):    
        print("{0} module got the following data: {1}".format(self.name, data))
        # look at mavlink and set self.is_not_armed
        # look at network and set have_path_to_cloud
        # look at webserver and set syncing_enabled
        pass
     
def init(in_queue, out_queue):
    '''initialise module'''
    return DFSyncModule(in_queue, out_queue)
    