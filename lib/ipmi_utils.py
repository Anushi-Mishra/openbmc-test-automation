#!/usr/bin/env python3

r"""
Provide useful ipmi functions.
"""

from robot.libraries.BuiltIn import BuiltIn
import re
import gen_print as gp
import gen_misc as gm
import gen_cmd as gc
import gen_robot_keyword as grk
import gen_robot_utils as gru
import bmc_ssh_utils as bsu
import var_funcs as vf
import ipmi_client as ic
import tempfile
import json
gru.my_import_resource("ipmi_client.robot")


def get_sol_info():
    r"""
    Get all SOL info and return it as a dictionary.

    Example use:

    Robot code:
    ${sol_info}=  get_sol_info
    Rpvars  sol_info

    Output:
    sol_info:
      sol_info[Info]:                                SOL parameter 'Payload Channel (7)'
                                                     not supported - defaulting to 0x0e
      sol_info[Character Send Threshold]:            1
      sol_info[Force Authentication]:                true
      sol_info[Privilege Level]:                     USER
      sol_info[Set in progress]:                     set-complete
      sol_info[Retry Interval (ms)]:                 100
      sol_info[Non-Volatile Bit Rate (kbps)]:        IPMI-Over-Serial-Setting
      sol_info[Character Accumulate Level (ms)]:     100
      sol_info[Enabled]:                             true
      sol_info[Volatile Bit Rate (kbps)]:            IPMI-Over-Serial-Setting
      sol_info[Payload Channel]:                     14 (0x0e)
      sol_info[Payload Port]:                        623
      sol_info[Force Encryption]:                    true
      sol_info[Retry Count]:                         7
    """

    status, ret_values = grk.run_key_u("Run IPMI Standard Command  sol info")

    # Create temp file path.
    temp = tempfile.NamedTemporaryFile()
    temp_file_path = temp.name

    # Write sol info to temp file path.
    text_file = open(temp_file_path, "w")
    text_file.write(ret_values)
    text_file.close()

    # Use my_parm_file to interpret data.
    sol_info = gm.my_parm_file(temp_file_path)

    return sol_info


def set_sol_setting(setting_name, setting_value):
    r"""
    Set SOL setting with given value.

    # Description of argument(s):
    # setting_name                  SOL setting which needs to be set (e.g.
    #                               "retry-count").
    # setting_value                 Value which needs to be set (e.g. "7").
    """

    status, ret_values = grk.run_key_u("Run IPMI Standard Command  sol set "
                                       + setting_name + " " + setting_value)

    return status


def execute_ipmi_cmd(cmd_string,
                     ipmi_cmd_type='inband',
                     print_output=1,
                     ignore_err=0,
                     **options):
    r"""
    Run the given command string as an IPMI command and return the stdout,
    stderr and the return code.

    Description of argument(s):
    cmd_string                      The command string to be run as an IPMI
                                    command.
    ipmi_cmd_type                   'inband' or 'external'.
    print_output                    If this is set, this function will print
                                    the stdout/stderr generated by
                                    the IPMI command.
    ignore_err                      Ignore error means that a failure
                                    encountered by running the command
                                    string will not be raised as a python
                                    exception.
    options                         These are passed directly to the
                                    create_ipmi_ext_command_string function.
                                    See that function's prolog for details.
    """

    if ipmi_cmd_type == 'inband':
        IPMI_INBAND_CMD = BuiltIn().get_variable_value("${IPMI_INBAND_CMD}")
        cmd_buf = IPMI_INBAND_CMD + " " + cmd_string
        return bsu.os_execute_command(cmd_buf,
                                      print_out=print_output,
                                      ignore_err=ignore_err)

    if ipmi_cmd_type == 'external':
        cmd_buf = ic.create_ipmi_ext_command_string(cmd_string, **options)
        rc, stdout, stderr = gc.shell_cmd(cmd_buf,
                                          print_output=print_output,
                                          ignore_err=ignore_err,
                                          return_stderr=1)
        return stdout, stderr, rc


def get_lan_print_dict(channel_number='', ipmi_cmd_type='external'):
    r"""
    Get IPMI 'lan print' output and return it as a dictionary.

    Here is an example of the IPMI lan print output:

    Set in Progress         : Set Complete
    Auth Type Support       : MD5
    Auth Type Enable        : Callback : MD5
                            : User     : MD5
                            : Operator : MD5
                            : Admin    : MD5
                            : OEM      : MD5
    IP Address Source       : Static Address
    IP Address              : x.x.x.x
    Subnet Mask             : x.x.x.x
    MAC Address             : xx:xx:xx:xx:xx:xx
    Default Gateway IP      : x.x.x.x
    802.1q VLAN ID          : Disabled
    Cipher Suite Priv Max   : Not Available
    Bad Password Threshold  : Not Available

    Given that data, this function will return the following dictionary.

    lan_print_dict:
      [Set in Progress]:                              Set Complete
      [Auth Type Support]:                            MD5
      [Auth Type Enable]:
        [Callback]:                                   MD5
        [User]:                                       MD5
        [Operator]:                                   MD5
        [Admin]:                                      MD5
        [OEM]:                                        MD5
      [IP Address Source]:                            Static Address
      [IP Address]:                                   x.x.x.x
      [Subnet Mask]:                                  x.x.x.x
      [MAC Address]:                                  xx:xx:xx:xx:xx:xx
      [Default Gateway IP]:                           x.x.x.x
      [802.1q VLAN ID]:                               Disabled
      [Cipher Suite Priv Max]:                        Not Available
      [Bad Password Threshold]:                       Not Available

    Description of argument(s):
    ipmi_cmd_type                   The type of ipmi command to use (e.g.
                                    'inband', 'external').
    """

    channel_number = str(channel_number)
    # Notice in the example of data above that 'Auth Type Enable' needs some
    # special processing.  We essentially want to isolate its data and remove
    # the 'Auth Type Enable' string so that key_value_outbuf_to_dict can
    # process it as a sub-dictionary.
    cmd_buf = "lan print " + channel_number + " | grep -E '^(Auth Type Enable)" +\
        "?[ ]+: ' | sed -re 's/^(Auth Type Enable)?[ ]+: //g'"
    stdout1, stderr, rc = execute_ipmi_cmd(cmd_buf, ipmi_cmd_type,
                                           print_output=0)

    # Now get the remainder of the data and exclude the lines with no field
    # names (i.e. the 'Auth Type Enable' sub-fields).
    cmd_buf = "lan print " + channel_number + " | grep -E -v '^[ ]+: '"
    stdout2, stderr, rc = execute_ipmi_cmd(cmd_buf, ipmi_cmd_type,
                                           print_output=0)

    # Make auth_type_enable_dict sub-dictionary...
    auth_type_enable_dict = vf.key_value_outbuf_to_dict(stdout1, to_lower=0,
                                                        underscores=0)

    # Create the lan_print_dict...
    lan_print_dict = vf.key_value_outbuf_to_dict(stdout2, to_lower=0,
                                                 underscores=0)
    # Re-assign 'Auth Type Enable' to contain the auth_type_enable_dict.
    lan_print_dict['Auth Type Enable'] = auth_type_enable_dict

    return lan_print_dict


def get_ipmi_power_reading(strip_watts=1):
    r"""
    Get IPMI power reading data and return it as a dictionary.

    The data is obtained by issuing the IPMI "power reading" command.  An
    example is shown below:

    Instantaneous power reading:                   234 Watts
    Minimum during sampling period:                234 Watts
    Maximum during sampling period:                234 Watts
    Average power reading over sample period:      234 Watts
    IPMI timestamp:                           Thu Jan  1 00:00:00 1970
    Sampling period:                          00000000 Seconds.
    Power reading state is:                   deactivated

    For the data shown above, the following dictionary will be returned.

    result:
      [instantaneous_power_reading]:              238 Watts
      [minimum_during_sampling_period]:           238 Watts
      [maximum_during_sampling_period]:           238 Watts
      [average_power_reading_over_sample_period]: 238 Watts
      [ipmi_timestamp]:                           Thu Jan  1 00:00:00 1970
      [sampling_period]:                          00000000 Seconds.
      [power_reading_state_is]:                   deactivated

    Description of argument(s):
    strip_watts                     Strip all dictionary values of the
                                    trailing " Watts" substring.
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  dcmi power reading")
    result = vf.key_value_outbuf_to_dict(ret_values)

    if strip_watts:
        result.update((k, re.sub(' Watts$', '', v)) for k, v in result.items())

    return result


def get_mc_info():
    r"""
    Get IPMI mc info data and return it as a dictionary.

    The data is obtained by issuing the IPMI "mc info" command.  An
    example is shown below:

    Device ID                 : 0
    Device Revision           : 0
    Firmware Revision         : 2.01
    IPMI Version              : 2.0
    Manufacturer ID           : 42817
    Manufacturer Name         : Unknown (0xA741)
    Product ID                : 16975 (0x424f)
    Product Name              : Unknown (0x424F)
    Device Available          : yes
    Provides Device SDRs      : yes
    Additional Device Support :
        Sensor Device
        SEL Device
        FRU Inventory Device
        Chassis Device
    Aux Firmware Rev Info     :
        0x00
        0x00
        0x00
        0x00

    For the data shown above, the following dictionary will be returned.
    mc_info:
      [device_id]:                       0
      [device_revision]:                 0
      [firmware_revision]:               2.01
      [ipmi_version]:                    2.0
      [manufacturer_id]:                 42817
      [manufacturer_name]:               Unknown (0xA741)
      [product_id]:                      16975 (0x424f)
      [product_name]:                    Unknown (0x424F)
      [device_available]:                yes
      [provides_device_sdrs]:            yes
      [additional_device_support]:
        [additional_device_support][0]:  Sensor Device
        [additional_device_support][1]:  SEL Device
        [additional_device_support][2]:  FRU Inventory Device
        [additional_device_support][3]:  Chassis Device
      [aux_firmware_rev_info]:
        [aux_firmware_rev_info][0]:      0x00
        [aux_firmware_rev_info][1]:      0x00
        [aux_firmware_rev_info][2]:      0x00
        [aux_firmware_rev_info][3]:      0x00
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  mc info")
    result = vf.key_value_outbuf_to_dict(ret_values, process_indent=1)

    return result


def get_sdr_info():
    r"""
    Get IPMI sdr info data and return it as a dictionary.

    The data is obtained by issuing the IPMI "sdr info" command.  An
    example is shown below:

    SDR Version                         : 0x51
    Record Count                        : 216
    Free Space                          : unspecified
    Most recent Addition                :
    Most recent Erase                   :
    SDR overflow                        : no
    SDR Repository Update Support       : unspecified
    Delete SDR supported                : no
    Partial Add SDR supported           : no
    Reserve SDR repository supported    : no
    SDR Repository Alloc info supported : no

    For the data shown above, the following dictionary will be returned.
    mc_info:

      [sdr_version]:                         0x51
      [record_Count]:                        216
      [free_space]:                          unspecified
      [most_recent_addition]:
      [most_recent_erase]:
      [sdr_overflow]:                        no
      [sdr_repository_update_support]:       unspecified
      [delete_sdr_supported]:                no
      [partial_add_sdr_supported]:           no
      [reserve_sdr_repository_supported]:    no
      [sdr_repository_alloc_info_supported]: no
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  sdr info")
    result = vf.key_value_outbuf_to_dict(ret_values, process_indent=1)

    return result


def get_aux_version(version_id):
    r"""
    Get IPMI Aux version info data and return it.

    Description of argument(s):
    version_id                      The data is obtained by from BMC
                                    /etc/os-release
                                    (e.g. "xxx-v2.1-438-g0030304-r3-gfea8585").

    In the prior example, the 3rd field is "438" is the commit version and
    the 5th field is "r3" and value "3" is the release version.

    Aux version return from this function 4380003.
    """

    # Commit version.
    count = re.findall("-(\\d{1,4})-", version_id)

    # Release version.
    release = re.findall("-r(\\d{1,4})", version_id)
    if release:
        aux_version = count[0] + "{0:0>4}".format(release[0])
    else:
        aux_version = count[0] + "0000"

    return aux_version


def get_fru_info():
    r"""
    Get fru info and return it as a list of dictionaries.

    The data is obtained by issuing the IPMI "fru print -N 50" command.  An
    example is shown below:

    FRU Device Description : Builtin FRU Device (ID 0)
     Device not present (Unspecified error)

    FRU Device Description : cpu0 (ID 1)
     Board Mfg Date        : Sun Dec 31 18:00:00 1995
     Board Mfg             : <Manufacturer Name>
     Board Product         : PROCESSOR MODULE
     Board Serial          : YA1934315964
     Board Part Number     : 02CY209

    FRU Device Description : cpu1 (ID 2)
     Board Mfg Date        : Sun Dec 31 18:00:00 1995
     Board Mfg             : <Manufacturer Name>
     Board Product         : PROCESSOR MODULE
     Board Serial          : YA1934315965
     Board Part Number     : 02CY209

    For the data shown above, the following list of dictionaries will be
    returned.

    fru_obj:
      fru_obj[0]:
        [fru_device_description]:  Builtin FRU Device (ID 0)
        [state]:                   Device not present (Unspecified error)
      fru_obj[1]:
        [fru_device_description]:  cpu0 (ID 1)
        [board_mfg_date]:          Sun Dec 31 18:00:00 1995
        [board_mfg]:               <Manufacturer Name>
        [board_product]:           PROCESSOR MODULE
        [board_serial]:            YA1934315964
        [board_part_number]:       02CY209
      fru_obj[2]:
        [fru_device_description]:  cpu1 (ID 2)
        [board_mfg_date]:          Sun Dec 31 18:00:00 1995
        [board_mfg]:               <Manufacturer Name>
        [board_product]:           PROCESSOR MODULE
        [board_serial]:            YA1934315965
        [board_part_number]:       02CY209
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  fru print -N 50")

    # Manipulate the "Device not present" line to create a "state" key.
    ret_values = re.sub("Device not present", "state : Device not present",
                        ret_values)

    return [vf.key_value_outbuf_to_dict(x) for x in re.split("\n\n",
                                                             ret_values)]


def get_component_fru_info(component='cpu',
                           fru_objs=None):
    r"""
    Get fru info for the given component and return it as a list of
    dictionaries.

    This function calls upon get_fru_info and then filters out the unwanted
    entries.  See get_fru_info's prolog for a layout of the data.

    Description of argument(s):
    component                       The component (e.g. "cpu", "dimm", etc.).
    fru_objs                        A fru_objs list such as the one returned
                                    by get_fru_info.  If this is None, then
                                    this function will call get_fru_info to
                                    obtain such a list.
                                    Supplying this argument may improve
                                    performance if this function is to be
                                    called multiple times.
    """

    if fru_objs is None:
        fru_objs = get_fru_info()
    return\
        [x for x in fru_objs
         if re.match(component + '([0-9]+)? ', x['fru_device_description'])]


def get_user_info(userid, channel_number=1):
    r"""
    Get user info using channel command and return it as a dictionary.

    Description of argument(s):
    userid          The userid (e.g. "1", "2", etc.).
    channel_number  The user's channel number (e.g. "1").

    Note: If userid is blank, this function will return a list of dictionaries.  Each list entry represents
    one userid record.

    The data is obtained by issuing the IPMI "channel getaccess" command.  An
    example is shown below for user id 1 and channel number 1.

    Maximum User IDs     : 15
    Enabled User IDs     : 1
    User ID              : 1
    User Name            : root
    Fixed Name           : No
    Access Available     : callback
    Link Authentication  : enabled
    IPMI Messaging       : enabled
    Privilege Level      : ADMINISTRATOR
    Enable Status        : enabled

    For the data shown above, the following dictionary will be returned.

    user_info:
      [maximum_userids]:     15
      [enabled_userids:      1
      [userid]               1
      [user_name]            root
      [fixed_name]           No
      [access_available]     callback
      [link_authentication]  enabled
      [ipmi_messaging]       enabled
      [privilege_level]      ADMINISTRATOR
      [enable_status]        enabled
    """

    status, ret_values = grk.run_key_u("Run IPMI Standard Command  channel getaccess "
                                       + str(channel_number) + " " + str(userid))

    if userid == "":
        return vf.key_value_outbuf_to_dicts(ret_values, process_indent=1)
    else:
        return vf.key_value_outbuf_to_dict(ret_values, process_indent=1)


def channel_getciphers_ipmi():

    r"""
    Run 'channel getciphers ipmi' command and return the result as a list of dictionaries.

    Example robot code:
    ${ipmi_channel_ciphers}=  Channel Getciphers IPMI
    Rprint Vars  ipmi_channel_ciphers

    Example output:
    ipmi_channel_ciphers:
      [0]:
        [id]:                                         3
        [iana]:                                       N/A
        [auth_alg]:                                   hmac_sha1
        [integrity_alg]:                              hmac_sha1_96
        [confidentiality_alg]:                        aes_cbc_128
      [1]:
        [id]:                                         17
        [iana]:                                       N/A
        [auth_alg]:                                   hmac_sha256
        [integrity_alg]:                              sha256_128
        [confidentiality_alg]:                        aes_cbc_128
    """

    cmd_buf = "channel getciphers ipmi | sed -re 's/ Alg/_Alg/g'"
    stdout, stderr, rc = execute_ipmi_cmd(cmd_buf, "external", print_output=0)
    return vf.outbuf_to_report(stdout)


def get_device_id_config():
    r"""
    Get the device id config data and return as a dictionary.

    Example:

    dev_id_config =  get_device_id_config()
    print_vars(dev_id_config)

    dev_id_config:
        [manuf_id]:            7244
        [addn_dev_support]:     141
        [prod_id]:            16976
        [aux]:                    0
        [id]:                    32
        [revision]:             129
        [device_revision]:        1
    """
    stdout, stderr, rc = bsu.bmc_execute_command("cat /usr/share/ipmi-providers/dev_id.json")

    result = json.loads(stdout)

    # Create device revision field for the user.
    # Reference IPMI specification v2.0 "Get Device ID Command"
    # [7]   1 = device provides Device SDRs
    #       0 = device does not provide Device SDRs
    # [6:4] reserved. Return as 0.
    # [3:0] Device Revision, binary encoded.

    result['device_revision'] = result['revision'] & 0x0F

    return result


def get_chassis_status():
    r"""
    Get IPMI chassis status data and return it as a dictionary.

    The data is obtained by issuing the IPMI "chassis status" command. An
    example is shown below:

    System Power              : off
    Power Overload            : false
    Power Interlock           : inactive
    Main Power Fault          : false
    Power Control Fault       : false
    Power Restore Policy      : previous
    Last Power Event          :
    Chassis Intrusion         : inactive
    Front-Panel Lockout       : inactive
    Drive Fault               : false
    Cooling/Fan Fault         : false
    Sleep Button Disable      : not allowed
    Diag Button Disable       : not allowed
    Reset Button Disable      : not allowed
    Power Button Disable      : allowed
    Sleep Button Disabled     : false
    Diag Button Disabled      : false
    Reset Button Disabled     : false
    Power Button Disabled     : false

    For the data shown above, the following dictionary will be returned.

    chassis_status:
      [system_power]:                        off
      [power_overload]:                      false
      [power_interlock]:                     inactive
      [main_power_fault]:                    false
      [power_control_fault]:                 false
      [power_restore_policy]:                previous
      [last_power_event]:
      [chassis_intrusion]:                   inactive
      [front-panel_lockout]:                 inactive
      [drive_fault]:                         false
      [cooling/fan_fault]:                   false
      [sleep_button_disable]:                not allowed
      [diag_button_disable]:                 not allowed
      [reset_button_disable]:                not allowed
      [power_button_disable]:                allowed
      [sleep_button_disabled]:               false
      [diag_button_disabled]:                false
      [reset_button_disabled]:               false
      [power_button_disabled]:               false
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  chassis status")
    result = vf.key_value_outbuf_to_dict(ret_values, process_indent=1)

    return result


def get_channel_info(channel_number=1):
    r"""
    Get the channel info and return as a dictionary.
    Example:

    channel_info:
      [channel_0x2_info]:
        [channel_medium_type]:                        802.3 LAN
        [channel_protocol_type]:                      IPMB-1.0
        [session_support]:                            multi-session
        [active_session_count]:                       0
        [protocol_vendor_id]:                         7154
      [volatile(active)_settings]:
        [alerting]:                                   enabled
        [per-message_auth]:                           enabled
        [user_level_auth]:                            enabled
        [access_mode]:                                always available
      [non-volatile_settings]:
        [alerting]:                                   enabled
        [per-message_auth]:                           enabled
        [user_level_auth]:                            enabled
        [access_mode]:                                always available
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  channel info " + str(channel_number))
    key_var_list = list(filter(None, ret_values.split("\n")))
    # To match the dict format, add a colon after 'Volatile(active) Settings' and 'Non-Volatile Settings'
    # respectively.
    key_var_list[6] = 'Volatile(active) Settings:'
    key_var_list[11] = 'Non-Volatile Settings:'
    result = vf.key_value_list_to_dict(key_var_list, process_indent=1)
    return result


def get_user_access_ipmi(channel_number=1):

    r"""
    Run 'user list [<channel number>]' command and return the result as a list of dictionaries.

    Example robot code:
    ${users_access}=  user list 1
    Rprint Vars  users_access

    Example output:
    users:
      [0]:
        [id]:                                         1
        [name]:                                       root
        [callin]:                                     false
        [link]:                                       true
        [auth]:                                       true
        [ipmi]:                                       ADMINISTRATOR
      [1]:
        [id]:                                         2
        [name]:                                       axzIDwnz
        [callin]:                                     true
        [link]:                                       false
        [auth]:                                       true
        [ipmi]:                                       ADMINISTRATOR
    """

    cmd_buf = "user list " + str(channel_number)
    stdout, stderr, rc = execute_ipmi_cmd(cmd_buf, "external", print_output=0)
    return vf.outbuf_to_report(stdout)


def get_channel_auth_capabilities(channel_number=1, privilege_level=4):
    r"""
    Get the channel authentication capabilities and return as a dictionary.

    Example:

    channel_auth_cap:
        [channel_number]:                               2
        [ipmi_v1.5__auth_types]:
        [kg_status]:                                    default (all zeroes)
        [per_message_authentication]:                   enabled
        [user_level_authentication]:                    enabled
        [non-null_user_names_exist]:                    yes
        [null_user_names_exist]:                        no
        [anonymous_login_enabled]:                      no
        [channel_supports_ipmi_v1.5]:                   no
        [channel_supports_ipmi_v2.0]:                   yes
    """

    status, ret_values = \
        grk.run_key_u("Run IPMI Standard Command  channel authcap " + str(channel_number) + " "
                      + str(privilege_level))
    result = vf.key_value_outbuf_to_dict(ret_values, process_indent=1)

    return result


def fetch_date(date):
    r"""
    Removes prefix 0 in a date in given date

    Example : 08/12/2021 then returns 8/12/2021
    """

    date = date.lstrip("0")
    return date


def fetch_added_sel_date(entry):
    r"""
    Split sel entry string with with | and join only the date with space

    Example : If entry given is, "a | 02/14/2020 | 01:16:58 | Sensor_type #0x17 |  | Asserted"
    Then the result will be "02/14/2020 01:16:58"
    """

    temp = entry.split(" | ")
    date = temp[1] + " " + temp[2]
    print(date)
    return date


def prefix_bytes(listx):
    r"""
    prefixes byte strings in list

    Example:
    ${listx} = ['01', '02', '03']
    ${listx}=  Prefix Bytes  ${listx}
    then,
    ${listx}= ['0x01', '0x02', '0x03']

    """

    listy = []
    for item in listx:
        item = "0x" + item
        listy.append(item)
    return listy


def modify_and_fetch_threshold(old_threshold, threshold_list):
    r"""
    Description of argument(s):

        old_threshold              List of threshold values of sensor,
        threshold_list             List of higher and lower of critical and non-critical values.
                                   i,e [ "lcr", "lnc", "unc", "ucr" ]

    Gets old threshold values from sensor and threshold levels,
    then returns the list of new threshold and the dict of threshold levels

    For example :
    1. If old_threshold list is [ 1, 2, 3, 4] then the newthreshold_list will be [ 101, 102, 103, 104 ].
       If old_threshold has 'na' the same will be appended to new list, eg: [ 101, 102, 103, 104, 'na'].

    2. The newthreshold_list will be zipped to dictionary with threshold_list levels,
       Example : threshold_dict = { 'lcr': 101, 'lnc': 102, 'unc': 103, 'ucr': 104 }

    """

    # Adding the difference of 100 as less than this value,
    # may not have greater impact as the sensor considered is a fan sensor.
    # The set threshold may round off for certain values below 100.
    n = 100
    newthreshold_list = []
    for th in old_threshold:
        th = th.strip()
        if th == 'na':
            newthreshold_list.append('na')
        else:
            x = int(float(th)) + n
            newthreshold_list.append(x)
            n = n + 100
    threshold_dict = dict(zip(threshold_list, newthreshold_list))
    return newthreshold_list, threshold_dict
