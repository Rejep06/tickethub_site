"""Small single-process scheduler; no in-memory business state or duplicate payment actions."""
import signal
import subprocess
import time

stopping = False

def stop(*_args):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
next_hour = 0.0
while not stopping:
    started = time.monotonic()
    commands = ['cleanup_expired_holds', 'cleanup_expired_quotes']
    if started >= next_hour:
        commands += ['cleanup_auth', 'remind_staff']
        next_hour = started + 3600
    for command in commands:
        if stopping: break
        try:
            result = subprocess.run(['python', 'manage.py', command], timeout=240, check=False)
            if result.returncode: print(f'Scheduler: {command} failed ({result.returncode}); see logs.', flush=True)
        except subprocess.TimeoutExpired:
            print(f'Scheduler: {command} timed out.', flush=True)
    while not stopping and time.monotonic() - started < 60: time.sleep(1)
