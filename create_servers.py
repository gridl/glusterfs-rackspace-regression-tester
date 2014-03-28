#!/usr/bin/env python
"""Times how long the GlusterFS regression test takes for each instance type
in Rackspace"""

import os
import sys
import getopt
import getpass
import time
import ConfigParser
import pyrax

version = '0.0.1'
max_servers = 1
delete_servers = False


def usage(error_string=None):
    prog_name = sys.argv[0]
    if error_string:
        print 'ERROR: {0}'.format(error_string)
        print
    print 'Usage:'
    print
    print '{0}'.format(prog_name)
    print '{0} [options]'.format(prog_name)
    print
    print '  -c | --cloud_init <file>  Provides the file to cloud-init'
    print '  -d | --delete             Delete the servers after creating them'
    print '  -h | --help               Display usage'
    print '  -n | --num_servers #      Create # number of servers'
    print
    print 'To create the default number of servers, use:'
    print
    print '  {0}'.format(prog_name)
    print
    print 'or to create a specific number of servers, use this:'
    print
    print '  {0} --num_servers #'.format(prog_name)
    print
    print 'To pass the servers a cloud-init configuration file, use:'
    print
    print '  {0} --cloud_init file'.format(prog_name)
    print
    print 'For example:'
    print
    print '  {0} --num_servers 5'.format(prog_name)
    print
    print 'or'
    print
    print '  {0} --cloud_init myfile.cfg --num_servers 10'.format(prog_name)
    print


# Display a startup banner
print 'Rackspace instance regression test timer: v{0}\n'.format(version)

# Check the command line
try:
    opts, args = getopt.getopt(sys.argv[1:], 'c:dhn:',
                               ['cloud_init=', 'delete', 'help',
                                'num_servers='])

except getopt.GetoptError as err:
    # There was something wrong with the command line options
    usage(err)
    sys.exit(2)

# Process any command line options and arguments
ci_config_obj = None
for o, a in opts:
    if o in ("-h", "--help"):
        usage()
        sys.exit()
    elif o in ("-c", "--cloud_init"):
        ci_config_path = os.path.expanduser(a)
        ci_config_obj = open(ci_config_path, 'r')
        ci_config = ci_config_obj.read()
    elif o in ("-n", "--num_servers"):
        max_servers = int(a)
    elif o in ("-d", "--delete"):
        delete_servers = True
    else:
        assert False, "Unknown command line option"

print "Creating {0} servers...".format(max_servers)
print

# Read config file
config_file_path = os.path.join('config')
config = ConfigParser.ConfigParser()
config.read(config_file_path)
creds_file = os.path.expanduser(config.get('credentials', 'rackspace'))
ssh_key_file = os.path.expanduser(config.get('credentials', 'ssh_key_file'))
ssh_key_name = config.get('credentials', 'ssh_key_name')

# Set the credentials for using Rackspace
pyrax.set_setting("identity_type", "rackspace")
pyrax.set_credential_file(creds_file)
cs = pyrax.cloudservers

# Select CentOS 6.5
centos = None
os_list = cs.images.list()
for os_option in os_list:
    if os_option.name == 'CentOS 6.5':
        centos = os_option

# Select a 1GB instance
instance = None
instance_list = cs.flavors.list()
for instance_option in instance_list:
    if instance_option.name == '1 GB Performance':
        instance = instance_option

# Start creating the servers
building_servers = []
building_passwords = []
username = getpass.getuser()
for counter in range(max_servers):
    node_name = '{0}-api-test-node{1}'.format(username, str(counter))
    print 'Creating {0}'.format(node_name)
    if ci_config:
        # Create a server + supply a cloud-init config
        building_servers.append(
            cs.servers.create(node_name, centos.id, instance.id,
                              key_name=ssh_key_name, config_drive=True,
                              userdata=ci_config))
    else:
        # Create a server without a cloud-init config
        building_servers.append(
            cs.servers.create(node_name, centos.id, instance.id,
                              key_name=ssh_key_name))
    building_passwords.append(building_servers[counter].adminPass)

# Wait 20 seconds (seems to help)
time.sleep(20)
print

# Wait until all of the servers are running
server_list = []
admin_passwords = []
for server in range(len(building_servers)):
    print 'Waiting for {0}'.format(building_servers[server].name)

    # Wait for the given server to become either ACTIVE or ERROR status
    finished_build = pyrax.utils.wait_until(building_servers[server],
                                            'status', ['ACTIVE', 'ERROR'],
                                            interval=30, attempts=8)

    # Check which status it changed to
    if finished_build.status == 'ACTIVE':
        print 'Success, {0} built correctly'.format(finished_build.name)

        # Add the server to the full list
        server_list.append(finished_build)
        admin_passwords.append(building_passwords[server])

    else:
        print 'Server {0} errored during creation, so deleting'.format(
            finished_build.name)
        finished_build.delete()

# Print out info for the servers
print
for counter in range(len(server_list)):
    server_list[counter] = cs.servers.get(server_list[counter].id)
    ip_addr = server_list[counter].accessIPv4
    print 'Server name: {0}'.format(server_list[counter].name)
    print 'Server ID: {0}'.format(server_list[counter].id)
    print 'IPv4 address: {0}'.format(ip_addr)
    print 'Root password: {0}'.format(admin_passwords[counter])
    print('SSH command: ssh -l root -i {0} -o UserKnownHostsFile=/dev/null '
          '-o StrictHostKeyChecking=no {1}'.format(ssh_key_file, ip_addr))
    print

# If requested, delete the servers (useful when testing)
if delete_servers:
    for counter in range(0, len(server_list)):
        print 'Deleting {0}'.format(server_list[counter].name)
        server_list[counter].delete()