from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import pid_exists, wait_pid
from APSyncFramework.utils.json_utils import json_wrap_with_target
from APSyncFramework.utils.file_utils import mkdir_p, write_config, read_config, file_get_contents
from APSyncFramework.utils.requests_utils import create_session, register, upload_request
from APSyncFramework.utils.network_utils import generate_key_fingerprint

import os, time, subprocess, uuid, shutil, signal, re, base64
from datetime import datetime
import requests

class DFSyncModule(APSync_module.APModule):
    def __init__(self, in_queue, out_queue):
        super(DFSyncModule, self).__init__(in_queue, out_queue, "dfsync")
        self.load_config()
        self.get_ssh_creds() # need ssh keys in place
        self.have_path_to_cloud = False # assume no internet facing network on module load
        self.is_not_armed = None # arm state is unknown on module load
        self.syncing_enabled = True
        self.cloudsync_session = False
        

        self.cloudsync_remote_dir = '~'
        self.datalog_dir = os.path.join(os.path.expanduser('~'), 'dflogger')
        self.datalog_archive_dir = os.path.join(os.path.expanduser('~'),'dflogger', 'dataflash-archive')
        # create us a ~/dflogger/ folder and ~/dflogger/dataflash-archive/  if it's not already there. 
        mkdir_p(self.datalog_dir)
        mkdir_p(self.datalog_archive_dir)
        self.old_time = 3 # seconds a file must remain unchanged before being considered okay to sync
        
        self.datalogs = {}
        self.rsync_pid = None
        self.rsync_time = re.compile(r'[0-9]:([0-5][0-9]):([0-5][0-9])')
        
        ### TODO update these values from other modules via process_in_queue_data()
        self.have_path_to_cloud = True
        self.is_not_armed = True
        self.syncing_enabled = True
        ###
        
        self.client = requests.Session()
        
        ###
        self.cloudsync_url_base = "https://"+self.cloudsync_address+"/"
        self.cloudsync_url_register = self.cloudsync_url_base+'register'
        self.cloudsync_url_upload = self.cloudsync_url_base+'upload'
    
    def load_config(self):
        # TODO: move some of this into the module lib...
        self.cloudsync_port = self.set_config('cloudsync_port', 22)
        self.cloudsync_user = self.set_config('cloudsync_user', 'apsync')
        self.cloudsync_address = self.set_config('cloudsync_address', 'apsync.cloud')
        self.cloudsync_account_registered = self.set_config('cloudsync_account_registered', 0)
        self.cloudsync_account_verified = self.set_config('cloudsync_account_verified', 0)
        self.cloudsync_ssh_identity_file = self.set_config('cloudsync_ssh_identity_file', os.path.expanduser('~/.ssh/id_apsync'))
        self.cloudsync_vehicle_id = self.set_config('cloudsync_vehicle_id', '')
        self.cloudsync_email = self.set_config('cloudsync_email', '')
        if self.config_changed:
            # TODO: send a msg to the webserver to update / reload the current page
            self.log("At least one of your cloudsync settings was missing or has been updated, please reload the webpage if open.", 'INFO')
            write_config(self.config)
            self.config_changed = False
    
    def main(self):
        if self.have_path_to_cloud:
            self.cloudsync_session = create_session(self.cloudsync_url_base, self.client)
            
            if (self.cloudsync_session and self.cloudsync_account_registered and not self.cloudsync_account_verified):
                # TODO - challenge verification
                pass
                
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
#             print self.datalogs
            if self.datalogs[key]['age'] > self.old_time:
                self.files_to_sync[key] = self.datalogs[key]['modify']
        # we have a dict of file names and last modified times
        self.files_to_sync = sorted(self.files_to_sync.items(), key = lambda x:x[1])
        
        if (len(self.files_to_sync) == 0 or not self.okay_to_sync()):
            time.sleep(2)
            return
        
        payload = {'public_key_fingerprint': base64.b64encode(self.ssh_cred_fingerprint), '_xsrf':self.client.cookies['_xsrf'] }
        upload_response = upload_request(self.cloudsync_url_upload, self.client, payload)
        self.log(upload_response, 'DEBUG')
        
        if not upload_response:
            time.sleep(2)
            return
        
        # sync the oldest file first
        file_to_send = self.files_to_sync[-1][0]
        send_path = os.path.join(self.datalog_dir,file_to_send)
        
        
        # upload_response
        archive_folder = upload_response['archive_folder']
        rsynccmd = '''rsync -ahHzv --progress -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -F /dev/null -i {0} -p {1}" "{2}" {3}@{4}:{5}'''.format(self.cloudsync_ssh_identity_file,
                                                                                                                                                                self.cloudsync_port,
                                                                                                                                                                send_path,
                                                                                                                                                                self.cloudsync_user,
                                                                                                                                                                self.cloudsync_address,
                                                                                                                                                                self.cloudsync_remote_dir)
        
        
        self.datalogs.pop(file_to_send)
        status_update = {'percent_sent':'0%', 'current_time':time.time(), 'file':file_to_send, 'status':'starting'}
        self.out_queue.put_nowait(json_wrap_with_target({'dfsync-sync_update' : status_update}, target = 'webserver'))
        
        rsyncproc = subprocess.Popen(rsynccmd,
                                     shell=True,
                                     stdin=None,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     universal_newlines=True,
                                    )                  
        self.rsync_pid = rsyncproc.pid
        while self.okay_to_sync():
            next_line = rsyncproc.stdout.readline().decode("utf-8")
            # TODO: log all of stdout to disk
            if self.rsync_time.search(next_line):
                # we found a line containing a status update
                current_status = next_line.strip().split()
                current_status = current_status[:4]
                current_status.append(str(time.time()))
                current_status.append(file_to_send)
                current_status.append('progress')
                # send this to the webserver...
                status_update = dict(zip(['data_sent', 'percent_sent', 'sending_rate', 'time_remaining', 'current_time', 'file', 'status'], current_status))
                self.out_queue.put_nowait(json_wrap_with_target({'dfsync-sync_update' : status_update}, target = 'webserver'))
                print {'dfsync-sync_update': status_update}
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
                archive_file_path = os.path.join(target_path, file_to_send)
                shutil.move(send_path, archive_file_path)
                status_update = {'percent_sent':'100%', 'current_time':time.time(), 'file':file_to_send, 'status':'complete'}
                self.out_queue.put_nowait(json_wrap_with_target({'dfsync-sync_update' : status_update}, target = 'webserver'))
                print('INFO: datalog rsync complete for {0}. Original datalog archived at {1}'.format(file_to_send, archive_file_path))
            else:
                error_lines = rsyncproc.stderr.readlines()
                err_trace = ''
                for line in error_lines:
                    err_trace += line.decode("utf-8")
                status_update = {'error':err_trace, 'current_time':time.time(), 'file':file_to_send, 'status':'error'}
                self.out_queue.put_nowait(json_wrap_with_target({'dfsync-sync_update' : status_update}, target = 'webserver'))
                print('WARNING: an error during datalog rsync for {0}, exit code: {1}, error trace: \n{2}'.format(file_to_send, exitcode, err_trace))
        else:
            self.request_rsync_exit()
            
    def request_rsync_exit(self):
        if not self.rsync_pid:
            return
        
        if pid_exists(self.rsync_pid):
            # the rsync process is required to exit
            print('INFO: attempting to stop rsync process')
        
            os.kill(self.rsync_pid, signal.SIGTERM)
            try:
                wait_pid(self.rsync_pid, timeout=0.1)
                timeout = False
            except:
                timeout = True
        
        if timeout and pid_exists(self.rsync_pid):
            os.kill(self.rsync_pid, signal.SIGKILL)
            try:
                wait_pid(self.rsync_pid, timeout=0.1)
                timeout = False
            except:
                timeout = True
                
        if timeout and pid_exists(self.rsync_pid):
            print("ERROR: failed to terminate and kill rsync process with pid: {0}".format(self.rsync_pid))
            
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
        if (self.is_not_armed and self.have_path_to_cloud and self.syncing_enabled and not self.needs_unloading.is_set() and self.cloudsync_session and self.cloudsync_account_registered and self.cloudsync_account_verified):
            return True
        else:
            return False
        
    def get_ssh_creds(self):
        ssh_cred_path = os.path.expanduser(self.cloudsync_ssh_identity_file+'.pub') # use the public key
        self.ssh_cred = file_get_contents(ssh_cred_path).strip() # need the '.strip()'!
        self.ssh_cred_fingerprint = generate_key_fingerprint(ssh_cred_path)
    
    def process_in_queue_data(self, data):    
        print("{0} module got the following data: {1}".format(self.name, data))
        if 'dfsync_register' in data.keys():
            for key in data['dfsync_register'].keys():
                self.config[key] = data['dfsync_register'][key]
            self.load_config()
            self.get_ssh_creds()
            # attempt registration with server
            if self.have_path_to_cloud:
                self.cloudsync_session = create_session(self.cloudsync_url_base, self.client)
                
            if self.cloudsync_session:
                
                payload = {'email': self.cloudsync_email, 'public_key': base64.b64encode(self.ssh_cred), '_xsrf':self.client.cookies['_xsrf'] }
                if register(self.cloudsync_url_register, self.client, payload):
                    # registration was OK
                    self.config['cloudsync_account_registered'] = 1
                    self.load_config()
                    # TODO: report registration attempt success 
                    self.log('Cloudsync registration attempt successful', 'INFO')
                    return
                
            self.config['cloudsync_account_registered'] = 0
            self.load_config()
            # TODO: report registration attempt fail
            self.log('Cloudsync registration attempt failed', 'INFO')
        # look at mavlink and set self.is_not_armed
        # look at network and set have_path_to_cloud
        # look at webserver and set syncing_enabled
        pass
    
        
    def unload_callback(self):
        self.request_rsync_exit()
        
def init(in_queue, out_queue):
    '''initialise module'''
    return DFSyncModule(in_queue, out_queue)
    