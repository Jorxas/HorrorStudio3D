"""python tools/blocking_deliver.py
Uploads the LIGHT mp4 (540x960) and the report of the continuity film to the ALREADY RUNNING local bridge mailbox (127.0.0.1 only, no tunnel touched, no token printed,
nothing published). The master stays on disk, untouched. For each file the server's SHA-256 and size are compared with the local file. Writes
projects/pompe_continuite_20261029/livraison/mailbox_delivery.json with file ids, sizes, hashes and absolute Windows paths."""
import hashlib, json, shutil, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; BASE = ROOT / 'projects' / 'pompe_continuite_20261029'; OUT = BASE / 'livraison'; OUT.mkdir(exist_ok=True)
NM = 'LA_DERNIERE_POMPE_partie1_CONTINUITE_VOXELGPU'
pairs = [(BASE / 'film' / 'leger.mp4', f'{NM}_leger_540x960.mp4'), (BASE / 'rapport_final.json', f'{NM}_rapport.json')]
files = []
for src, dst in pairs: shutil.copyfile(src, OUT / dst); files.append(OUT / dst)
state = Path.home() / '.claude-code-bridge'
cfg = json.loads((state / 'config.json').read_text(encoding='utf-8-sig')).get('cloud_mailbox') or {}
assert cfg.get('enabled') is True, 'boîte aux lettres désactivée'
base = f"http://127.0.0.1:{int(cfg.get('port', 18765))}"; H = {'Authorization': 'Bearer ' + (state / 'mailbox' / 'token').read_text(encoding='utf-8').strip()}
with urllib.request.urlopen(urllib.request.Request(base + '/v1/ping', headers=H), timeout=10) as r: assert json.load(r)['ok']
rec = {}
for p in files:
    data = p.read_bytes(); dg = hashlib.sha256(data).hexdigest(); mime = {'.mp4': 'video/mp4', '.json': 'application/json'}[p.suffix]
    assert len(data) <= 90 * 1048576, 'fichier trop gros pour un seul envoi'
    req = urllib.request.Request(base + '/v1/files?name=' + urllib.parse.quote(p.name), data=data, headers=dict(H, **{'Content-Type': mime}), method='POST')
    with urllib.request.urlopen(req, timeout=600) as r: meta = json.load(r)
    assert meta['ok'] and meta['sha256'] == dg and meta['bytes'] == len(data), "le serveur n'a pas confirmé la même empreinte"
    stored = state / 'mailbox' / 'files' / f"{meta['file_id']}.bin"; back = hashlib.sha256(stored.read_bytes()).hexdigest() if stored.exists() else None
    rec[p.name] = dict(file_id=meta['file_id'], bytes=meta['bytes'], sha256=dg, local_path=str(p.resolve()), stored_bytes_sha256_ok=(back == dg) if back else 'non relu')
    print(p.name, meta['file_id'], meta['bytes'], 'octets ; empreinte confirmée ; relue sur disque :', 'OK' if back == dg else back)
(OUT / 'mailbox_delivery.json').write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
