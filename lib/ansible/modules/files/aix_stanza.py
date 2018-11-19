#!/usr/bin/python
# -*- coding: utf-8 -*-


from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: aix_stanza

short_description: modify aix stanza files

version_added: "0.1"

description:
    - "adds stanza lines/addr/value pairs, changes attr/value pairs, removes stanzas/attr/value pairs"

options:
    path:
        description:
            - Path to the stanza file
        required: true
    stanza:
        description:
            - name of add_stanza
        required: true
    options:
         description:
             - comman separated key/value pairs eg. key=val,key=val
    backup:
    description:
      - Create a backup file including the timestamp information so you can get
        the original file back if you somehow clobbered it incorrectly.
    type: bool
    default: 'no'
  state:
     description:
       - If set to C(absent) the stanza will be removed if present instead of created.
     choices: [ absent, present ]
     default: present
  others:
     description:
       - All arguments accepted by the M(file) module also work here

extends_documentation_fragment:
    - files

author:
    - Christian Tremel (@flynn1973)
'''

EXAMPLES = '''
- name: add ldap user stanza
  aix_stanza:
    path: /etc/security/user
    stanza: exampleuser
    options: SYSTEM=LDAP,registry=LDAP
    state: present
    mode: 0644
    backup: yes

- name: add filesystem entry
  aix_stanza:
    path: /etc/filesystems
    stanza: /examplemount
    options: dev=/dev/lvosystem_c,vfs=jfs2,log=INLINE,mount=true
    state: present
    backup: yes
'''


import os
import re
import tempfile
import traceback
from ansible.module_utils.basic import *

import pdb; pdb.set_trace()


def do_stanza(module, filename, stanza, options, state='present', backup=False, create=True):

    diff = dict(
        before='',
        after='',
        before_header='%s (content)' % filename,
        after_header='%s (content)' %  filename,
    )

    if not os.path.exists(filename):
        if not create:
            module.fail_json(rc=257, msg='Destination %s does not exist !' % filename)
        destpath = os.path.dirname(filename)
        if not os.path.exists(destpath) and not module.check_mode:
            os.makedirs(destpath)
        stanza_lines = []
    else:
        stanza_file = open(filename, 'r')
        try:
            stanza_lines = stanza_file.readlines()
        finally:
            stanza_file.close()

    if module._diff:
        diff['before'] = ''.join(stanza_lines)

    changed = False

    # stanza file may be empty so add at least a newline
    if not stanza_lines:
        stanza_lines.append('\n')

     # last line should always be a newline to keep up with POSIX standard
    if stanza_lines[-1] == "" or stanza_lines[-1][-1] != '\n':
        stanza_lines[-1] += '\n'
        changed = True

    # append fake stanza lines to simplify the logic
    # Fake random stanza to avoid matching anything  other in the file
    # Using commit hash as fake stanza name
    fake_stanza_name = "ad01e11446efb704fcdbdb21f2c43757423d91c5"

    # Insert it at the beginning
    stanza_lines.insert(0, '[%s]' % fake_stanza_name)

    # At botton:
    stanza_lines.append(':')

    # If no sstanza is defined, fake stanza is used
    if not stanza:
        stanza = fake_stanza_name

    within_stanza = not stanza
    stanza_start = 0
    msg = 'OK' 


    stanza_format = '\n%s:\n'
    option_format = '\t%s = %s\n'


    for index, line in enumerate(stanza_lines):
        if line.startswith('%s:' % stanza):
            within_stanza = True
            stanza_start = index
            if within_stanza:
                if state == 'present':
                    # insert missing option lines at the end of the stanza 
                    for i in range(index, 0, -1):
                        # search backwards for previous non-blank or non-comment lines
                        if not re.match('^[ \t]*([#;].*)?$', stanza_lines[i - 1]):
                                # loop through options dict
                                for opt in list(options.keys()):
                                    stanza_lines.insert(i, option_format % (opt, options[opt]))
                                    msg = 'options added'
                                    changed = True
                                    break
                elif state == 'absent' and not options:
                    # remove the entire stanza if no option lines present
                    del stanza_lines[stanza_start:index]
                    msg = 'stanza removed'
                    changed = True
                    break
            else:
                if within_stanza and options:
                    if state == 'present':
                        # loop through options dict
                        for opt in list(options.keys()):
                            # change existing option lines
                            if re.match('(^\t%s = %s$)' % opt, options[opt]):
                                newline = option_format % (opt, options[opt])
                                option_changed = stanza_lines[index] != newline
                                changed = changed or option_changed
                                if option_changed:
                                    msg = 'option changed'
                                stanza_lines[index] = newline
                                if option_changed:
                                    # remove all possible option occurrences from the stanza 
                                    index = index + 1
                                    while index < len(stanza_lines):
                                        line = stanza_lines[index]
                                        if re.match('(^\t%s = %s$)' % opt, options[opt]):
                                            del stanza_lines[index]
                                        else:
                                            index = index + 1
                                break
                    elif state == 'absent':
                        # loop through options dict
                        for opt in list(options.keys()):
                            # delete the existing line
                            if re.match('(^\t%s = %s$)' % opt, options[opt]):
                                del stanza_lines[index]
                                changed = True
                                msg = 'option removed'
                                break

    # remove the fake stanza lines
    del stanza_lines[0]
    del stanza_lines[-1:]

    if not within_stanza and options and state == 'present':
        stanza_lines.append(stanza_format % stanza)
        # loop through options dict
        for opt in list(options.keys()):
            stanza_lines.append(option_format % (opt, options[opt]))
            changed = True
            msg = 'stanza and option added'

    if module._diff:
        diff['after'] = ''.join(stanza_lines)

    backup_file = None
    if changed and not module.check_mode:
        if backup:
            backup_file = module.backup_local(filename)

        try:
            tmpfd, tmpfile = tempfile.mkstemp(dir=module.tmpdir)
            f = os.fdopen(tmpfd, 'w')
            f.writelines(stanza_lines)
            f.close()
        except IOError:
            module.fail_json(msg="Unable to create temporary file %s", traceback=traceback.format_exc())

        try:
            module.atomic_move(tmpfile, filename)
        except IOError:
            module.ansible.fail_json(msg='Unable to move temporary \
                                   file %s to %s, IOError' % (tmpfile, filename), traceback=traceback.format_exc())

    return (changed, backup_file, diff, msg)


def main():

    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='path', required=True, aliases=['dest']),
            stanza=dict(type='str', required=True),
            options=dict(type='dict', required=True),
            backup=dict(type='bool', default=False),
            state=dict(type='str', default='present', choices=['absent', 'present']),
            create=dict(type='bool', default=True)
        ),
        add_file_common_args=True,
        supports_check_mode=True,
    )

    path = module.params['path']
    stanza = module.params['stanza']
    options = module.params['options']
    state = module.params['state']
    backup = module.params['backup']
    create = module.params['create']

    (changed, backup_file, diff, msg) = do_stanza(module, path, stanza, options, state, backup, create)


    if not module.check_mode and os.path.exists(path):
        file_args = module.load_file_common_arguments(module.params)
        changed = module.set_fs_attributes_if_different(file_args, changed)

    results = dict(
        changed=changed,
        diff=diff,
        msg=msg,
        path=path,
    )
    if backup_file is not None:
        results['backup_file'] = backup_file

    # Mission complete
    module.exit_json(**results)

if __name__ == '__main__':
    main()
