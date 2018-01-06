import datetime
import logging
import logging.config
import re
import socket
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

import ntplib
import numpy as np
import pandas as pd
import paramiko
import pytz

from api_config import log_config, main_config

logging.config.dictConfig(log_config)
logger = logging.getLogger("tools")

# ---
"""Retry calling the decorated function using an exponential backoff.
   http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
   original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
   :param ExceptionToCheck: the exception to check. may be a tuple of
       exceptions to check
   :type ExceptionToCheck: Exception or tuple
   :param tries: number of times to try (not retry) before giving up
   :type tries: int
   :param delay: initial delay between retries in seconds
   :type delay: int
   :param backoff: backoff multiplier e.g. value of 2 will double the delay
       each retry
   :type backoff: int
   :param logger: logger to use. If None, print
   :type logger: logger.Logger instance
"""


def retry(ExceptionToCheck, tries=4, delay=1, backoff=2):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "{}, Retrying in {} seconds...".format(str(e), mdelay)
                    if logging:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


# ---

def datetime_diference(datatime_a, datatime_b):
    try:
        if isinstance(datatime_a, str):
            datatime_a = datetime.strptime(datatime_a, "%Y-%m-%d %H:%M:%S")
        if isinstance(datatime_b, str):
            datatime_b = datetime.strptime(datatime_b, "%Y-%m-%d %H:%M:%S")

        datatime_a = localize(datatime_a, pytz.UTC)
        datatime_b = localize(datatime_b, pytz.UTC)

        if (datatime_a > datatime_b):
            return (datatime_a - datatime_b).seconds
        else:
            return (datatime_b - datatime_a).seconds
    except Exception as e:
        print("Problem with check diff time".format(e))


'''
    format(e.g., 2016-10-03T23:00:00Z).
'''


def datetime_iso8601(dt):
    # d = datetime.datetime.strptime("2017-10-13T10:53:53.000Z", "%Y-%m-%dT%H:%M:%S.000Z")
    # iso8601 = dt.strftime("%Y-%m-%dT%H:%M.000Z")
    iso8601 = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return iso8601


'''
Return a data with tzinfo
'''


def localize(dt, tz):
    if dt.tzinfo is not None:
        return dt
    else:
        return dt.replace(tzinfo=tz)


def convert_local_utc(local_date, local_timezone):
    utc = pytz.utc
    local_zone = pytz.timezone(local_timezone)
    local_dt = local_zone.localize(local_date)
    return local_dt.astimezone(utc)


@retry(Exception, tries=4)
def query_ntp(ntp_server, version=3):
    for ntpsrv in ntp_server:
        try:
            c = ntplib.NTPClient()
            response = c.request(ntpsrv, version=version)
            utctime = datetime.utcfromtimestamp(response.tx_time).strftime("%Y-%m-%d %H:%M:%S")
            return utctime
        except:
            continue


def convert_bool_to_int(value):
    try:
        if isinstance(value, bool):
            if value:
                return 1
            else:
                return 0
        if isinstance(value, str):
            if value.lower() == "yes" or value.lower() == "true" or value == "1" or value.lower() == "on":
                return 1
            elif value.lower() == "no" or value.lower() == "false" or value == "1" or value.lower() == "off":
                return 0
            else:
                return value
        else:
            return value
    except:
        logger.error("Error to convert bool to int")
    finally:
        return value


def convert_anything_to_bool(value):
    boolvalue = False
    try:
        if isinstance(value, bool):
            boolvalue = value

        if isinstance(value, int):
            if value == "1":
                boolvalue = True

        if isinstance(value, str):
            if value.lower() == "yes" or value.lower() == "true" or value == "1" or value.lower() == "on" or value.lower() == "sim":
                boolvalue = True
    except Exception as e:
        logger.error("Error to convert anything to bool ")
    finally:
        return boolvalue


def nan2floatzero(value):
    try:
        if np.isnan(value):
            return 0.0
        else:
            return float(value)
    except Exception as e:
        logger.error("Error to convert NaN value to 0.00 - {}".format(e))


def findNumber(text):
    return (re.findall(r'\d+', text))[0]


def sshCommand(command, hostname, username, tcpport=22, password=None, pkey=None):
    ssh_timeout = 1
    try:
        ssh_timeout = general_config.getint('ssh_timewout_seconds', fallback=ssh_timeout)
    except:
        pass

    kword = {}
    kword['hostname'] = hostname
    kword['port'] = tcpport
    kword['username'] = username
    if password is not None:
        kword['password'] = password
    if pkey is not None:
        kword['pkey'] = paramiko.RSAKey.from_private_key_file(pkey)
    kword['compress'] = False
    fulloutput = None
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.debug("ssh connected on host {}".format(hostname))
        ssh.connect(**kword)
        stdin, stdout, stderr = ssh.exec_command(command, get_pty=True, timeout=ssh_timeout)
        stdin.flush()
        fulloutput = ""
        for line in iter(stdout.readline, ""):
            fulloutput += line
        return fulloutput
    except (socket.error, paramiko.AuthenticationException, paramiko.SSHException, Exception) as authe:
        logger.warning("Error to user {}, ssh_key {}, {}".format(username, pkey, authe))
    finally:
        ssh.close()


"""
https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=34e431b0ae398fc54ea69ff85ec700722c9da773
MemAvailable: An estimate of how much memory is available for starting new applications, without swapping.
"""


def parseMemInfo(str_mem):
    status = {}
    for line in str_mem.split('\n'):
        try:
            key = line.strip().split()[0].split(':')[0]
            value = line.strip().split()[1]
            status[key.lower()] = (float(value))
        except:
            pass
    return status


def calc_available_percent_memory(dict_mem_info):
    perc = None
    try:
        # if 'memavailable' in dict_mem_info.keys():
        #     total = float(dict_mem_info['memtotal'].replace('kB',''))
        #     available = float(dict_mem_info['memavailable'].replace('kB',''))
        # else: # Kernel antigo / CentOS  6
        #     total = float(dict_mem_info['memtotal'].replace('kB',''))
        #     free = float(dict_mem_info['memfree'].replace('kB',''))
        #     perc = round(((free * 100) / total),2)

        # http://elixir.free-electrons.com/linux/v4.0.9/source/fs/proc/meminfo.c
        if 'low_watermark' in dict_mem_info.keys():
            if dict_mem_info['low_watermark'] is not None or dict_mem_info['low_watermark'] > 0:
                low_watermark = dict_mem_info['low_watermark']
                total = float(dict_mem_info['memtotal'].replace('kB', '')) * 1024
                free = float(dict_mem_info['memfree'].replace('kB', '')) * 1024
                sreclaimable = float(dict_mem_info['sreclaimable'].replace('kB', '')) * 1024
                files_inactive = float(dict_mem_info['inactive(file)'].replace('kB', '')) * 1024
                files_active = float(dict_mem_info['active(file)'].replace('kB', '')) * 1024
                # Calculation...
                # available = (free + pagecache + sreclaimable) - low_watermark
                available = free - low_watermark
                pagecache = (files_active + files_inactive)
                pagecache -= low_watermark
                available += pagecache
                available += sreclaimable - (sreclaimable / 2);

                availablekb = "{} kB".format(int(available / 1024))
                perc = round(((available * 100) / total), 2)
    except Exception as e:
        print(e)
        pass
    return perc, availablekb


def check_is_file_exist(file):
    my_file = Path(file)
    if not my_file.is_file():
        logger.warning("File {} not found".format(file))
        return False
    else:
        return True


def check_file_permission(file):
    my_file = Path(file)
    if not my_file.is_file():
        return None
    st = my_file.stat()
    oct_perm = oct(st.st_mode)[-4:]
    return oct_perm


def convert_dict_dataframe(dict):
    columns = list(dict.keys())
    values = list(dict.values())
    arr_len = len(values)
    df = pd.DataFrame(np.array(values, dtype=object).reshape(1, arr_len), columns=columns)
    return df


def concat_frames(list_frames):
    frames = [list_frames]
    return pd.concat(frames)


def find_key_in_dict(key, dictionary):
    for k, v in dictionary.iteritems():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in find_key_in_dict(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in find_key_in_dict(key, d):
                    yield result


def get_timestp():
    timestamp = int(time.time())
    return timestamp


def ssh_os_linux_available_memory(host_ip, host_key=None, username=None, password=None):
    kword = {}
    dict_mem_full_info = {'percent_free': 0,
                          'memtotal': 0,
                          'memavailable': 0,
                          'kernel': 'unknown',
                          'distro': 'unknown'
                          }

    if host_key is not None:
        if not ".pem" in host_key:
            host_key += ".pem"
        key_path = main_config['aws_ssh_key_folder']
        if key_path[:1] == '/':
            key_path += "{}".format(host_key)
        else:
            key_path += '/{}'.format(host_key)
        if not check_file_permission(key_path) == '0600':
            logger.warning(
                "Error of file not found {} in folder {}".format(host_key, main_config['aws_ssh_key_folder']))
            return dict_mem_full_info
        kword['pkey'] = key_path
    elif password is not None:
        kword['password'] = password
    else:
        return dict_mem_full_info

    if username is None:
        os_usernames = ['ec2-user', 'centos', 'ubuntu', 'root']
    else:
        os_usernames = [username]

    for username in os_usernames:
        logger.debug("Getting memory info through SSH")
        low_watermark = 0
        PAGESIZE = 4096
        dict_ssh_return = {}
        try:
            kword['username'] = username
            kword['hostname'] = host_ip

            # First command...
            kword['command'] = "cat /proc/zoneinfo| grep low| awk '{print $2}'"
            result_commands = sshCommand(**kword)
            if not result_commands:
                return dict_mem_full_info
            for line in result_commands.split('\n'):
                if line == "":
                    break
                low_watermark += (int(line) * PAGESIZE)  # or sum(line) * 12k
            dict_ssh_return['low_watermark'] = low_watermark

            # Getting the rest os informations...
            kword['command'] = "cat /proc/meminfo | grep Mem ;" \
                               "cat /proc/meminfo | grep -w \"Mapped\"; " \
                               "cat /proc/vmstat  | grep nr_mapped ;  " \
                               "cat /proc/meminfo | grep \"Active(file)\" ;  " \
                               "cat /proc/meminfo | grep \"Inactive(file)\"; " \
                               "cat /proc/meminfo | grep \"SReclaimable\" ; " \
                               "echo \"Kernel: $(uname -r)\"; " \
                               "echo \"Distro: $(cat /etc/issue|head -1)\" "

            # The above commands returns in Key/Value format, so we need to convert in python key/value
            result_commands = sshCommand(**kword)
            for line in result_commands.split('\n'):
                if line == "":
                    break
                key = str(line.strip().split()[0]).replace(':', '')
                value = str(line.strip().split()[1])
                dict_ssh_return[key.lower()] = value

            # Now. we need to convert this information in data...
            dict_mem_full_info['percent_free'] = calc_available_percent_memory(dict_ssh_return)[0]
            dict_mem_full_info['memavailable'] = calc_available_percent_memory(dict_ssh_return)[1]
            dict_mem_full_info['memtotal'] = dict_ssh_return['memtotal']
            dict_mem_full_info['kernel'] = dict_ssh_return['kernel']
            dict_mem_full_info['distro'] = dict_ssh_return['distro']

            # Case success, break the "user" loop.
            if dict_mem_full_info['percent_free'] is not None:
                break
        except Exception:
            dict_mem_full_info['percent_free'] = 0.00
            dict_mem_full_info['memavailable'] = 0.00
            dict_mem_full_info['memtotal'] = 0.00
            dict_mem_full_info['kernel'] = None
            dict_mem_full_info['distro'] = None
            logger.exception("Error on Getting memory info throughSSH: {}".format(kword), exc_info=False)
        finally:
            return dict_mem_full_info


def df_to_picke(df, file):
    try:
        df.to_pickle(file)
    except Exception as e:
        logger.error("Error to save dataframe to pickle file {} - {}".format(file, e))


def picke_to_dataframe(file):
    if check_is_file_exist(file):
        try:
            df = pd.read_pickle(file)
            return df
        except Exception as e:
            logger.error("The file exist but I can convert picke file to dataframe")
    else:
        logger.error("Error with file, maybe it's not existe or cannot open")


def check_string_in_list(string, list):
    match = False
    for item in list:
        pattern = re.compile("{}".format(item), re.IGNORECASE)
        if pattern.match(string):
            match = True
    return match


def config_fallback(value, fallback=None):
    try:
        if value is None:
            return fallback
        return value
    except Exception:
        logger.exception("Error to process value or fallback", exc_info=True)
