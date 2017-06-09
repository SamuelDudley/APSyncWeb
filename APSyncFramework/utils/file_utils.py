import sys
import os
import json
from os import listdir, rename
from os.path import isfile, join, getmtime, dirname, realpath
import re
import time
import errno

# determine current directory, as it's the "root" of the Web
if  sys.platform == 'win32':
    # and this is for windows:   1\\2\\3\\4
    WinAppRoot = dirname(realpath(__file__))
    #  ensure double back slashes on windows, as that the convention we are using.
    WinAppRoot = WinAppRoot.replace('\\', '\\\\') # replace a single backslash with a double, trust me.  :-) 
else:
    # this is used for non-windows platforms with posix filesystems ( ie 1/2/3/4 )
    AppRoot =  dirname(realpath(__file__))+"/.."   #eg '/root/WebConfigServer'

def read_config():

        if sys.platform == 'win32':
            filename = WinAppRoot+'\\conf\\WebConfigServer.windows.json'
        else:
            filename = os.path.join(AppRoot,'conf','WebConfigServer.json')

        #return json.loads(file_get_contents(filename))
        config = None
        try:  # we need both a file-on-disk, AND valid JSON inside 
            config =  json.loads(file_get_contents(filename))
        except:
            print "ERROR: unable to read JSON from %s, maybe it doesn't exist or is invalis JSON" %filename
        return config


def read_master_wifi():
        if sys.platform == 'win32':
            filename = WinAppRoot+'\\conf\\masterwifi.windows.json'
        else:
            filename = AppRoot+'/conf/masterwifi.json'

        return json.loads(file_get_contents(filename))

def write_master_wifi(json_data):
        if sys.platform == 'win32':
            dirname = WinAppRoot+'\\conf\\'
            filename = dirname+'masterwifi.windows.json'
        else:
            dirname = AppRoot+'/conf/'
            filename = dirname+'masterwifi.json'

        cleaned = json.dumps(json_data,indent=2,sort_keys=True)       # json->string

        file_put_contents(filename,cleaned)  # put the string

        return True


def write_config(json_data):
        if sys.platform == 'win32':
            dirname = WinAppRoot+'\\conf\\'
            filename = dirname+'WebConfigServer.windows.json'
        else:
            filename = os.path.join(AppRoot,'conf','WebConfigServer.json')

        old = read_config() # for something to compage against before we change it.

        cleaned = json.dumps(json_data,indent=2,sort_keys=True)       # json->string

        file_put_contents(filename,cleaned)  # put the string

        # ... 

        return True

def read_passwd_file():
        config = read_config()
        passwords = {}
        # theoretically supports multiple passwordss up to this point, in reality we just have one. 
        content = config['basicauth']
        if ":" in content: 
            username, password = content.split(":")
            passwords[username] = password
        return passwords

    # don't diss me for using the php function name/s, ok. 
def file_put_contents(filename,data):
        f = open(filename, 'w')
        f.write(data)
        # to get it truly on disk:
        f.flush()
        os.fsync(f.fileno())
        # then close it
        f.close()



def file_get_contents(filename):
        maxlen = 10000
        fp = open(filename,'rb')
        try:
            ret = fp.read(maxlen)
            return ret
        finally:
            fp.close( )
        return ""

# returns first suitable filename on disk if one is found otherwise empty string. other files found are returned by following calls when first file is removed.
# ignore ones containing in .done in the name
def check_crontab_queue():
        if sys.platform == 'win32':
            dirname = WinAppRoot+'\\cronqueue\\'
        else:
            dirname = AppRoot+'/cronqueue/'
        for f in os.listdir(dirname):
            fname = join(dirname, f);
            if isfile(fname) and (fname.find(".json") >= 0) and (fname.find(".done") == -1) :
                print "found a JSON file to action:"+fname
                return fname
        return ""

# overwrite masterwifi.json 
# decider should be 1 or 2 ( to say which of the sets of wifi credentials to get from WebConfigServer.json )
def write_new_master(decider):
    
    conf = read_config()

    print "write_new_master:"+str(decider)

    if decider == 1:
        msrc="wifitest.py-1"
        mpwd=conf['pwd1']
        mssid=conf['ssid1']
    if decider == 2:
        msrc="wifitest.py-2"
        mpwd=conf['pwd2']
        mssid=conf['ssid2']

    message = '''{
              "mpwd": "'''+mpwd+'''", 
              "msrc": "'''+msrc+'''", 
              "mssid": "'''+mssid+'''"
            }'''

    json_data = json.loads(message)  # string -> json object

    write_master_wifi(json_data)   # writes object to disk

    # so we know which ssid it was...
    return mssid


# this uses the credentials in masterwifi.env, and puts them into /etc/network/interfaces
def do_interfaces_file():

    vars = read_master_wifi()

    SSID=vars['mssid']
    PASSWORD=vars['mpwd']

    print SSID
    print PASSWORD

    interfacesfile = '/etc/network/interfaces'
    interfacescontent = '''
    # this file is AUTOGENERATED by wifitest.py, do not edit by hand unless you sure.
    #lo
    auto lo
    iface lo inet loopback

    #eth0
    #  we also had to  apt-get purge ifplugd for this
    #auto eth0
    iface eth0 inet manual
    allow-hotplug eth0  

    #wlan0
    #allow-hotplug wlan0
    #auto wlan0
    iface wlan0 inet dhcp
       wpa-essid '''+SSID+'''
       wpa-psk '''+PASSWORD+'''
       dns-nameservers 8.8.8.8 8.8.4.4

    #wlan1
    #allow-hotplug wlan1
    #auto wlan1
    iface wlan1 inet static
       address 10.10.10.1
       netmask 255.255.255.0
       post-up '''+AppRoot+'''/tools/post-up-wlan1.sh > /blah/hostapd-postup.log &

    up iptables-restore < /etc/iptables.ipv4.nat
    '''

    # create new - uncomment this to actually change the file programatically.
    # file_put_contents(interfacesfile,interfacescontent)

# internal utility 
def _getMacAddress(): 
    if sys.platform == 'win32': 
        for line in os.popen("ipconfig /all"): 
            if line.lstrip().startswith('Physical Address'): 
                mac = line.split(':')[1].strip().replace('-',':') 
                break 
    else: 
        for line in os.popen("/sbin/ifconfig"): 
            if line.find('Ether') > -1: 
                mac = line.split()[4] 
                break 
    return mac

def read_my_mac_address():

    if sys.platform == 'win32':
        dirname = WinAppRoot+'\\conf\\'
        filename = dirname+'my_mac_serial.windows.json'
    else:
        dirname = AppRoot+'/conf/'
        filename = dirname+'my_mac_serial.json'

    mymac = file_get_contents(filename)
    return mymac.lstrip().rstrip().lower()

def write_my_mac_address(mac=None):

    if sys.platform == 'win32':
        conffolder = WinAppRoot+'\\conf\\'
        thefile = 'my_mac_serial.windows.json'
    else:
        conffolder = AppRoot+'/conf/'
        thefile = 'my_mac_serial.json'


    if mac ==None:
        # read from OS if we weren't given one...
        mac = _getMacAddress()

    # save the current MAC here: for other uses: 
    file_put_contents(conffolder+thefile,mac) 
    return mac


# we only change it if it's not None.    valid values are None, 0, 1
def change_leds(r=None,g=None,b=None):

    if sys.platform == 'win32':
        folder = WinAppRoot+'\\tools\\'
        thefile = 'leds.windows.json'
    else:
        folder = '/tmp/'
        thefile = 'leds.json'

    ledstates = file_get_contents(folder+thefile)
    leds = json.loads(ledstates)
    R = int(leds['red'])
    G = int(leds['green'])
    B = int(leds['blue'])
    #print "R: %d G: %d B: %d " % ( R , G , B ) 
    if r != None:
        leds['red'] = r
    if g != None:
        leds['green'] = g
    if b != None:
        leds['blue'] = b

    # if anything changed, write it out....
    if (r != R ) or ( g != G ) or ( b != B ) : 
        file_put_contents(folder+thefile,json.dumps(leds))


# https://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
