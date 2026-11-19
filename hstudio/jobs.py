"""Background jobs (one at a time per project) with progress and log, for the web interface."""
import threading, time, traceback

class Job:
    def __init__(self, key, name):
        self.key = key; self.name = name; self.state = 'running'; self.progress = 0.; self.detail = ''
        self.log = []; self.started = time.time(); self.ended = None; self.result = None
    def write(self, msg):
        self.log.append(f'[{time.strftime("%H:%M:%S")}] {msg}'); self.log = self.log[-400:]
    def prog(self, p, detail=''):
        self.progress = float(p); self.detail = detail
    def as_dict(self):
        return {'key': self.key, 'name': self.name, 'state': self.state, 'progress': self.progress, 'detail': self.detail,
                'log': self.log[-120:], 'started': self.started, 'ended': self.ended, 'result': self.result}

JOBS = {}
LOCK = threading.Lock()

def start(key, name, fn):
    with LOCK:
        j = JOBS.get(key)
        if j and j.state == 'running': raise RuntimeError(f'Une tâche est déjà en cours : {j.name}')
        j = Job(key, name); JOBS[key] = j
    def run():
        try:
            j.result = fn(j); j.state = 'done'; j.progress = 1.; j.write('Terminé.')
        except Exception as e:
            j.state = 'error'; j.write(f'ERREUR : {e}'); j.write(traceback.format_exc()[-1500:])
        finally: j.ended = time.time()
    threading.Thread(target=run, daemon=True).start()
    return j

def get(key):
    j = JOBS.get(key); return j.as_dict() if j else None
