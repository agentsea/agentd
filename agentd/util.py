import os
import pwd
import subprocess


def run_as_user(command, username):
    # Get the user's UID and GID
    pw_record = pwd.getpwnam(username)
    user_uid = pw_record.pw_uid
    user_gid = pw_record.pw_gid

    def preexec_fn():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return subprocess.Popen(command, preexec_fn=preexec_fn)

def log_subprocess_output(pipe, sub_process):
    for line in iter(pipe.readline, b''): # b'\n'-separated lines
        if line:  # Check if the line is not empty
            print(f'from subprocess: {sub_process} got line: {line.strip()}', flush=True)