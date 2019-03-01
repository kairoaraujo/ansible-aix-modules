#!/usr/bin/python

from ansible.module_utils.basic import *

import os, subprocess, re

# AIX emgr ansible module with support for --check mode
# Author: Vasiliy Gokoyev
# 
# Examples:
#
#
#  - name: Install xorgs ifix /foo/bar/xorg_fix3/IJ11544s0a.181127.epkg.Z
#    emgr:
#      package: /foo/bar/xorg_fix3/IJ11544s0a.181127.epkg.Z
#      state: present
#
#  - name: Remove ifix with label IJ11544s0a
#    emgr:
#      label: IJ11544s0a
#      state: absent
# 


def main():
	
	fields = {
		"label" : {"required": False, "type": 'str'},
		"package" : {"required": False, "type": 'str'},
		"state" : {
			"default": "present",
			"choices": ['present', 'absent'],
			"type": 'str'
		},
	}

	module = AnsibleModule(argument_spec=fields, supports_check_mode=True)

	label = module.params['label']
	package = module.params['package']
	state = module.params['state']

	if state == 'present':

		if package is None:
			module.fail_json(msg="package path/filename is required to install ifix")
		
		label = _get_ifix_label(package)

		if label is None:
			module.fail_json(msg = ("Invalid package file or unable to get ifix label from %s" % package))
	
		if _ifix_installed(label):
			changed = False
			msg = ("Ifix already installed: %s" % label)
		else:
			if not module.check_mode and _install_ifix_pkg(package):
				changed = True
				msg = ("IFIX package with label {0} has been installed".format(label))
			elif module.check_mode:
				changed = True
				msg = ("IFIX package with label {0} would be installed".format(label))
			else:
				module.fail_json(msg = ("Failed to install ifix from %s" % package))

	elif state == 'absent':
		

		if label is None:
			module.fail_json(msg = "Ifix label is required to uninstall ifix")
				
		if _ifix_installed(label):
			if not module.check_mode and _remove_ifix_pkg(label):
				changed = True
				msg = ("IFIX package with label {0} has been removed".format(label))
			elif module.check_mode:
				changed = True
				msg = ("IFIX package with label {0} would be removed".format(label))
			else:
				module.fail_json(msg = ("Failed to uninstall ifix %s" % label))
		else:
			changed = False
			msg = ("Ifix is not installed: %s" % label)


	else:
		changed = False
        	msg = "Unexpected state."
        	module.fail_json(msg=msg)

    	module.exit_json(changed=changed, msg=msg)


def _get_ifix_label(package):
	# gets ifix label from the ifix package file (.Z)
	command = ["emgr"]
	command.extend(["-d",  "-e", package])
	result = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
	output = result.communicate()[0]
	labels = re.findall("LABEL:\s+(\w+)",output)
	returncode = result.returncode
	if returncode is 0 and len(labels) > 0:
		return labels[0]
	else:
		return None

def _ifix_installed(label):
	# checks if an ifix with given label is installed on the system
	command = ["emgr"]
	command.extend(["-c", "-L", label])
	result = subprocess.Popen(command)
	output = result.communicate()[0]
	returncode = result.returncode
	if returncode is 0:
		return True
	else:
		return False

def _install_ifix_pkg(package):
	# installs ifix given package file
	command = ["emgr"]
	command.extend(["-e", package])
	result = subprocess.Popen(command)
	output = result.communicate()[0]
	returncode = result.returncode
	if returncode is 0:
		return True
	else:
		return False

def _remove_ifix_pkg(label):
	command = ["emgr"]
	command.extend(["-r", "-L", label])
	result = subprocess.Popen(command)
	output = result.communicate()[0]
	returncode = result.returncode
	if returncode is 0:
		return True
	else:
		return False
	

if __name__ == '__main__':
	main()
