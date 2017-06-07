# python calls to linux shell commands
# unsure if network manager will be used long term...

import subprocess, time
import os

def run(args, shell = False):
    try:
        p = subprocess.check_output(args, stderr=subprocess.STDOUT, shell=shell).decode("utf-8")
#         print p # prints the output if any for a zero return
        return (0, p)
    except OSError as e: # bad command
#         print e
        # TODO: log this error
        return
    except subprocess.CalledProcessError as e: # non zero return
#         print e.returncode # the non zero return code
#         print e.cmd # the cmd that caused it
#         print e.output # the error output (if any)  
        return (e.returncode, e.output)
        
def make_ssh_key(key_path = os.path.join(os.path.expanduser('~'), '.ssh'), key_name = 'id_apsync'):
    
    args = ["ssh-keygen", "-t", "rsa", "-f", os.path.join(key_path, key_name), "-N", ""]
    print str(args)
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return

    print str(output)
    for line in output.split('\n'):
        if 'transmitted' in line.strip():
            print line
            # we could do something with this output if desired...
            
    if returncode == 0:   
        return 
    else:
        return False

def generate_key_fingerprint(key_path):
    args = ['ssh-keygen', '-lf', key_path]
    ret = run(args)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
         
    if returncode == 0:   
        return output.strip().split(' ')[1].strip()
    else:
        return False

def ping(ip, interface = "wlan0"):
    print("Pinging {0} on {1}".format(ip, interface))
    args = ["ping", "-c", "2", "-I", str(interface), str(ip)]
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return

    for line in output.split('\n'):
        if 'transmitted' in line.strip():
            print line
            # we could do something with this output if desired...
            
    if returncode == 0:   
        return True
    else:
        return False
    
def get_internet_status(interface = "wlan0"):
    ping('google.com', interface = interface)

def get_wifi_aps(password, interface):
    args = "echo '{0}' | sudo -S wpa_cli -i {1} scan".format(password, interface)
    attempt_count = 0
    result = None
    while attempt_count < 10:
        ret = run(args, shell = True)
        try:
            (returncode, output) = ret
        except ValueError:
            # bad command
            return
        if returncode == 0:
            output = output.strip().split(' ')[-1]
            result = output.strip()
            if 'OK' in result:
                result = True
                break
            result = False
        
        if returncode == 255:
            # not a wifi interface?
            print 'ERROR: {0}'.format(output).strip()
            return False
            
        time.sleep(1)
        attempt_count += 1
        
    if not result:
        print 'ERROR: {0}'.format(output).strip()
        return
    
    args = "echo '{0}' | sudo -S wpa_cli scan_results | grep PSK".format(password)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    if returncode == 0:
        wifi = {}
        output = output.split('\n')
        for ent in output:
            ent = ent.split(' ')[-1]
            ent = ent.split('\t')
            if len(ent) == 5:
                wifi[ent[4]] = {'mac':ent[0], 'freq':ent[1], 'signal':ent[2], 'enc':ent[3]}
        return wifi
    
    else:
        return False
 
def get_wifi_status(password, interface):
    args = "echo '{0}' | sudo -S wpa_cli -i {1} status".format(password, interface)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    if returncode == 0:   
        wifi = {}
        output = output.rstrip().split('\n')
        for ent in output:
            ent = ent.split(' ')[-1].strip("'")
            ent = ent.split('=')
            if len(ent) == 2:
                wifi[ent[0]] = ent[1]
            else:
                wifi['interface'] = ent[0]
        return wifi
        
    if returncode == 255:
            # not a wifi interface?
            print 'ERROR: {0}'.format(output).strip()
            return False
        
def restart_interface(password, interface = 'wlan0'):
    args = "echo '{0}' | sudo -S ifdown {1}".format(password, interface)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
        print ret
    except ValueError:
        # bad command
        return
    
    args = "echo '{0}' | sudo -S ifup {1}".format(password, interface)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
        print ret
    except ValueError:
        # bad command
        return
    
def search_string(line, _string):
    _sub_string = _string.split(' ')[-1].strip()
    try:
        idx = line.index(_string)
        sub_line = line[idx+len(_string):]
        return sub_line.split(' ')[0].strip()
    except ValueError:
        return

def get_network_interfaces():
    args = ["ifconfig"]
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    interfaces = {}
    details = {}
    new_interface = True
    for line in output.split('\n')[:-1]: # drop the last line
        if new_interface:
            interface = line.split(' ')[0].strip()
            new_interface = False
            
        elif line == '':
            new_interface = True
            # save the details from the last interface
            if interface:
                interfaces[interface] = details
            # reset the current interface detials
            interface = None
            details = {}
        
        else:
            for val in ['RX packets:', 'TX packets:', 'HWaddr ', 'inet addr:', 'Mask:', 'RX bytes:', 'TX bytes:', 'Bcast:' ]:
                ret = search_string(line, val)
                if ret:
                    details[val.strip().strip(':')] = ret
                    
    if returncode == 0:
        return interfaces
    else:
        return False

def get_serial_ids():
    args = ['ls', '/dev/serial/by-id/*']
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return

def shutdown(password):
    args = "echo '{0}' | sudo -S shutdown -h now".format(password)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return

def reboot(password):
    args = "echo '{0}' | sudo -S reboot now".format(password)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
def nmcli_add_wifi_conn_client(ssid, wifi_key, interface = 'wlan0',  conn_name="WiFiClient"):
    connections = nmcli_c()
    if not (connections or isinstance(connections, dict)):
        # nmcli not supported?
        return
    
    arg_list = []
    
    connection = connections.get(conn_name, None)
    if connection:
        print("INFO: a connection named '{0}' already exists, skipping creation".format(conn_name))
    else:
        args = "nmcli connection add con-name {0} type wifi ifname {1} ssid {2}".format(conn_name, interface, ssid)
        arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} connection.autoconnect no".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} 802-11-wireless.mode infrastructure".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} wifi-sec.key-mgmt wpa-psk".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} 802-11-wireless-security.auth-alg open".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} wifi-sec.psk {1}".format(conn_name, wifi_key)
    arg_list.append(args.split(' '))
    args = "nmcli connection up {0}".format(conn_name)
    arg_list.append(args.split(' '))
    
    for args in arg_list:
        ret = run(args, shell = False)
        try:
            (returncode, output) = ret
        except ValueError:
            # bad command
            return
    
        if returncode != 0:
            # TODO: log this
            print ret, arg_list
            return False
        
        if output != '':
            print output.strip()
    
    return True

def nmcli_add_wifi_conn_ap(ssid='ardupilot', wifi_key='enRouteArduPilot', interface = 'wlan0',  conn_name='WiFiAP', band = 'bg'):
    supported_bands = ['bg', 'a'] # TODO: obtain these values for the interface
    # see https://unix.stackexchange.com/questions/184175/how-to-set-up-wifi-hotspot-with-802-11n-mode for 'n' mode support
    if band not in supported_bands:
        print("WARNING: band '{0}' is not supported, valid options are 'bg' or 'a'. Defaulting to 'bg'".format(band))
        band = 'bg'
    connections = nmcli_c()
    if not (connections or isinstance(connections, dict)):
        # nmcli not supported?
        return
    
    arg_list = []
    
    connection = connections.get(conn_name, None)
    if connection:
        print("INFO: a connection named '{0}' already exists, skipping creation".format(conn_name))
    else:
        args = "nmcli connection add con-name {0} type wifi ifname {1} ssid {2}".format(conn_name, interface, ssid)
        arg_list.append(args.split(' '))
        
    args = "nmcli connection modify {0} connection.autoconnect no".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} 802-11-wireless.mode ap 802-11-wireless.band {1} ipv4.method shared".format(conn_name, band)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} wifi-sec.key-mgmt wpa-psk".format(conn_name)
    arg_list.append(args.split(' '))
    args = "nmcli connection modify {0} wifi-sec.psk {1}".format(conn_name, wifi_key)
    arg_list.append(args.split(' '))
    args = "nmcli connection up {0}".format(conn_name)
    arg_list.append(args.split(' '))
    
    for args in arg_list:
        ret = run(args, shell = False)
        try:
            (returncode, output) = ret
        except ValueError:
            # bad command
            return
    
        if returncode != 0:
            # TODO: log this
            print ret, arg_list
            return False
        
        if output != '':
            print output.strip()
    
    return True

def nmcli_restart(password):
    args = "echo '{0}' | sudo -S service network-manager restart".format(password)
    ret = run(args, shell = True)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    if returncode == 0:
        return True
    else:
        return False


def nmcli_c():
    args = ['nmcli', 'c']
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    if returncode == 0:
        output = output.strip().split('\n')
        connections = {}
        for ent in output:
            if 'NAME' in ent:
                col_names = ent.strip().lower().split()
            else:
                ent = ent.strip().split()
                connections[ent[0]] = dict(zip(col_names[1:], ent[1:]))
        
        return connections
    else:
        return False

def nmcli_d():
    args = ['nmcli', 'd']
    ret = run(args, shell = False)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
    
    if returncode == 0:
        output = output.strip().split('\n')
        interfaces = {}
        for ent in output:
            if 'DEVICE' in ent:
                col_names = ent.strip().lower().split()
            else:
                ent = ent.strip().split()
                interfaces[ent[0]] = dict(zip(col_names[1:], ent[1:]))
        
        return interfaces
    
    else:
        return False

# need to check if the wifi device supports AP mode iw list (look for AP)
# then use iw dev to match the phy# to a device

# can't seem to go from AP mode back to client mode without requiring a restart of network manager
# need to do the following:
# nmcli_add_wifi_conn_ap()
# nmcli_restart()
# nmcli_add_wifi_conn_client()