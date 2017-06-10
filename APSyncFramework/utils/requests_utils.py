from APSyncFramework.utils.network_utils import make_ssh_key, generate_key_fingerprint
from APSyncFramework.utils.file_utils import mkdir_p, file_get_contents
import requests, sys, base64

debug = True # TODO:replace with logging

def create_session(URL, client):
    # Retrieve the CSRF token first
    if not client.cookies.get('_xsrf', False):
        # we dont have a xsrf cookie yet...
        try:
            r = client.get(URL, verify=True) # sets cookie
            if check_response(r):
                if client.cookies.get('_xsrf', False):
                    # we now have a xsrf cookie
                    return True
                else:
                    # the response from the server was OK,
                    # however we failed to get a xsrf cookie from the server
                    return False
            else:
                # the response from the server was bad
                return False
        except Exception as e:
            print('An exception has occured accessing {0}.\n{1}'.format(URL, e))
    else:
        # we have an existing xsrf cookie for this session
        return True
    
def check_response(r):
    try:
        r.raise_for_status()
    except Exception as e:
        print('An error occured when handling your request: {0} - {1}\n{2}'.format(r.status_code, r.url, e))
        return False
    if debug:
        print('{0} - {1}'.format(r.status_code, r.url))
    return True

def register(URL, client, payload):
    r = client.post(URL, data=payload, verify=True)
    if check_response(r):
        r_dict = r.json()
        return r_dict
    return False

def verify(URL, client, payload):
    r = client.post(URL, data=payload, verify=True)
    if check_response(r):
        r_dict = r.json()
        return r_dict
    return False

def upload_request(URL, client, payload):
    r = client.post(URL, data=payload, verify=True)
    if check_response(r):
        r_dict = r.json()
        return r_dict
    return False

if __name__ == '__main__':
    import subprocess, os
    
    verified_with_server = False # set to True once you have registed with your public key and email
    user_email_address = 'example@gmail.com' # verification email will be sent here
    ssh_cred_name = 'id_apsync' # will be made if it does not exist
    file_to_upload = '~/dflogger/APSync.log'# ~/example.txt
    
    file_to_upload = os.path.expanduser(file_to_upload)
    ssh_cred_folder = os.path.join(os.path.expanduser('~'), '.ssh')
    mkdir_p(ssh_cred_folder) # make the dir if it does not exist
    ssh_cred_path = os.path.join(ssh_cred_folder, ssh_cred_name+'.pub') # only expose the public key?
    if not os.path.isfile(ssh_cred_path):
        make_ssh_key(ssh_cred_folder, ssh_cred_name)
    ssh_cred = file_get_contents(ssh_cred_path).strip() # need the '.strip()'!
    
    client = requests.Session()
    
    URL0 = "https://apsync.cloud/"
    URL1 = "https://apsync.cloud/register"
    URL2 = "https://apsync.cloud/verify?hash="
    URL3 = "https://apsync.cloud/upload"
    
    if not verified_with_server:
        # register
        if create_session(URL0, client):
            payload = {'email': user_email_address, 'public_key': base64.b64encode(ssh_cred), '_xsrf':client.cookies['_xsrf'] }
            if register(URL1, client, payload):
                print('verify your details via your email before re-running with "verified_with_server = True"')
    else:
        # check to see if the upload file exists
        if not os.path.isfile(file_to_upload):
            print('Could not find file: {0}'.format(file_to_upload))
            sys.exit(1)
        
        if create_session(URL0, client):
            payload = {'public_key_fingerprint': base64.b64encode(generate_key_fingerprint(ssh_cred_path)), '_xsrf':client.cookies['_xsrf'] }
            upload_request(URL3, client, payload)
    
            rsynccmd = '''rsync -ahHzv --progress -e "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -F /dev/null -i {0} -p 22" "{1}" apsync@apsync.cloud:~'''.format(os.path.join(ssh_cred_folder, ssh_cred_name), file_to_upload)
            rsyncproc = subprocess.Popen(
                                        rsynccmd,
                                        shell=True,
                                        stdin=None,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True,
                                        )
            for line in rsyncproc.stdout.readlines():
                print(line)                  
            exitcode = rsyncproc.wait()
            print('rsync exit code: {0}'.format(exitcode))