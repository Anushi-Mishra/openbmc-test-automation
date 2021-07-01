*** Settings ***
Documentation   Test BMC multiple network interface functionalities.

# User input BMC IP for the eth1.
# Use can input as  -v OPENBMC_HOST_1:xx.xxx.xx from command line.
Library         ../../lib/bmc_redfish.py  https://${OPENBMC_HOST_1}:${HTTPS_PORT}
...             ${OPENBMC_USERNAME}  ${OPENBMC_PASSWORD}  WITH NAME  Redfish1

Resource        ../../lib/resource.robot
Resource        ../../lib/common_utils.robot
Resource        ../../lib/connection_client.robot
Resource        ../../lib/bmc_network_utils.robot
Resource        ../../lib/openbmc_ffdc.robot

Suite Setup     Suite Setup Execution
Test Teardown   FFDC On Test Case Fail


*** Test Cases ***

Verify Both Interfaces BMC IP Addreeses Accessible Via SSH
    [Documentation]  Verify both interfaces (eth0, eth1) BMC IP addresses accessible via SSH.
    [Tags]  Verify_Both_Interfaces_BMC_IP_Addresses_Accessible_Via_SSH

    Open Connection And Log In  ${OPENBMC_USERNAME}  ${OPENBMC_PASSWORD}  host=${OPENBMC_HOST}
    Open Connection And Log In  ${OPENBMC_USERNAME}  ${OPENBMC_PASSWORD}  host=${OPENBMC_HOST_1}
    Close All Connections


Verify Redfish Works On Both Interfaces
    [Documentation]  Verify access BMC with both interfaces (eth0, eth1) IP addresses via Redfish.
    [Tags]  Verify_Redfish_Works_On_Both_Interfaces
    [Teardown]  Run Keywords
    ...  Configure Hostname  ${hostname}  AND  Validate Hostname On BMC  ${hostname}

    Redfish1.Login
    Redfish.Login

    ${hostname}=  Redfish.Get Attribute  ${REDFISH_NW_PROTOCOL_URI}  HostName
    ${data}=  Create Dictionary  HostName=openbmc
    Redfish1.patch  ${REDFISH_NW_ETH_IFACE}eth1  body=&{data}
    ...  valid_status_codes=[${HTTP_OK}, ${HTTP_NO_CONTENT}]

    Validate Hostname On BMC  openbmc

    ${resp1}=  Redfish.Get  ${REDFISH_NW_ETH_IFACE}eth0
    ${resp2}=  Redfish1.Get  ${REDFISH_NW_ETH_IFACE}eth1
    Should Be Equal  ${resp1.dict['HostName']}  ${resp2.dict['HostName']}

*** Keywords ***

Get Network Configuration Using Channel Number
    [Documentation]  Get ethernet interface.
    [Arguments]  ${channel_number}

    # Description of argument(s):
    # channel_number   Ethernet channel number, 1 is for eth0 and 2 is for eth1 (e.g. "1").

    ${active_channel_config}=  Get Active Channel Config
    ${ethernet_interface}=  Set Variable  ${active_channel_config['${channel_number}']['name']}
    ${resp}=  Redfish.Get  ${REDFISH_NW_ETH_IFACE}${ethernet_interface}

    @{network_configurations}=  Get From Dictionary  ${resp.dict}  IPv4StaticAddresses
    [Return]  @{network_configurations}


Suite Setup Execution
    [Documentation]  Do suite setup task.

    Valid Value  OPENBMC_HOST_1

    # Check both interfaces are configured and reachable.
    Ping Host  ${OPENBMC_HOST}
    Ping Host  ${OPENBMC_HOST_1}
