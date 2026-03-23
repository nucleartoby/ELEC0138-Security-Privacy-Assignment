#!/usr/bin/env python3

import sys
import subprocess
import os
import errno
import signal
import time
import argparse
import datetime
import yaml
import random
import shutil
import getpass

__author__ = 'chepeftw'

numberOfNodesStr = '20'
emulationTimeStr = '600'
churn = '0'
ns3FileLog = '0'
scenarioSize = '5'
network = 'csma'
numberOfNodes = 0
devs=0
jobs = max(1, os.cpu_count() - 1)
nameList = []

baseContainerNameConn = 'myconnmanbox'
baseContainerNameDnsm = 'mydnsmasqbox'
baseContainerNameAtt = 'myattackbox'

pidsDirectory = "./var/pid/"

ns3Version=''
with open('network/ns3_version') as f:
    ns3Version = str.strip(f.readline())

def main():
    global numberOfNodesStr, \
        emulationTimeStr, \
        churn, \
        ns3FileLog, \
        network, \
        scenarioSize, \
        numberOfNodes, \
        nameList, \
        devs, \
        jobs

    parser = argparse.ArgumentParser(description="DDoSim Implementation.", add_help=True)
    parser.add_argument("operation", action="store", type=str, choices=['create', 'ns3', 'emulation', 'destroy'], help="The name of the operation to perform, options: create, ns3, emulation, destroy")

    parser.add_argument("-n", "--number", action="store",type=int, help="The number of nodes to simulate")

    parser.add_argument("-t", "--time", action="store", type=int, help="The time in seconds of NS3 simulation")

    parser.add_argument("-net", "--network", action="store", type=str, choices=['csma', 'wifi'], help="The type of network, options: csma, wifi")

    parser.add_argument("-ch", "--churn", action="store", type=str, choices=['0', '1', '2'], help="Enable Nodes churn, options: 0, 1, or 2 ; these options are: no churn, static, or dynamic")

    parser.add_argument("-l", "--log", action="store", type=str, choices=['0', '1', '2'], help="Log from NS3 to File, options: 0, 1, or 2 ; these options are: no log, pcap only, or log pcap and statistics. If log is enabled, the files will be stored in desktop")

    parser.add_argument("-s", "--size", action="store", help="The size in meters of NS3 network simulation")

    parser.add_argument("-j", "--jobs", action="store", type=int, help="The number of parallel jobs")

    parser.add_argument('-v', '--version', action='version', version='%(prog)s 3.0')

    parser.add_argument("-d", "--devs", action="store", type=int, choices=[0 , 1 , 2], help="Used software for Devs, options: 0, 1, or 2 ; these options are: Connman, Dnsmasq, or both (Connman and Dnsmasq). If both is enabled, Devs will be assigned Connman or Dnsmasq randomly")

    args, unknown = parser.parse_known_args()

    if len(unknown):
        print('\x1b[6;30;41m' + '\nUnknown arument: ' +str(unknown)+ '\x1b[0m')
        parser.print_help()
        sys.exit(2)

    if args.number:
        numberOfNodesStr = args.number
    if args.time:
        emulationTimeStr = args.time
    if args.network:
        network = args.network
    if args.churn:
        churn = args.churn
    if args.log:
        ns3FileLog = args.log
    if args.size:
        scenarioSize = args.size
    if args.devs:
        devs = args.devs
    if args.jobs:
        jobs = int(args.jobs)

    operation = args.operation

    print("\nOperation : %s" % operation)
    print("Number of nodes : %s" % numberOfNodesStr)
    print("Simulation time : %s" % emulationTimeStr)
    print("Network Type : %s" % network)
    print("Churn : %s" % ("no churn" if churn=='0' else "static churn" if churn=='1' else "dynamic churn"))
    print("NS3 File Log : %s" % ("disabled" if ns3FileLog=='0' else "enabled"))
    print("Devs : %s" % ("Connman" if devs==0 else "Dnsmasq" if devs==1 else "Connman and Dnsmasq"))

    if network == 'wifi':
        print("Scenario Size (Disk): %s" % (scenarioSize))

    print("\t")
    os.environ["NS3_HOME"] = "./network/ns-allinone-"+ns3Version+"/ns-"+ns3Version

    os.environ["DOCKER_CLI_EXPERIMENTAL"] = "enabled"

    numberOfNodes = int(numberOfNodesStr) + 1 # TServer

    if numberOfNodes < 3:
        print("number of nodes should be 2 or more")
        sys.exit(2)

    global base_name
    base_name = "emu"

    for x in range(0, numberOfNodes+2): # we are not using emu0 or emu1
        nameList.append(base_name + str(x))

    if operation == "create":
        create()
    elif operation == "destroy":
        destroy()
    elif operation == "ns3":
        ns3()
    elif operation == "emulation":
        run_emu()
    else:
        print("Nothing to be done")

def check_return_code(rcode, message):
    if rcode == 0:
        print("\nSuccess: %s" % message)
        return

    print("\nError: %s" % message)
    print('\x1b[6;30;41m' + 'STOP! Please investigate the previous error(s) and run the command again' + '\x1b[0m')
    destroy()  # Adding this in case something goes wrong, at least we do some cleanup
    sys.exit(2)

def check_return_code_chill(rcode, message):
    if rcode == 0:
        print("\nSuccess: %s" % message)
        return

    print("\nError: %s" % message)
    return

def nodes_in_pid_dir():
    return max([int(name.split(base_name)[1]) if (name.split(base_name)[1]) else 0 for name in os.listdir(pidsDirectory) if len(name.split(base_name)) > 1])

def verify_num_nodes():
    docker_files = 0
    if os.path.exists(pidsDirectory):
        if os.listdir(pidsDirectory):
            docker_files =  nodes_in_pid_dir()
            if docker_files != (numberOfNodes):
                print('Please correct the number of nodes (-n %d) in the command'%(docker_files))
                sys.exit(2)
        else:
            print("Run the 'create' command and try again")
            sys.exit(2)
    else:
        print("Run the 'create' command and try again")
        sys.exit(2)

def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

