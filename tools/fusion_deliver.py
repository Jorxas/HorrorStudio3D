"""python tools/fusion_deliver.py [--no-master]
Uploads the fusion film (light mp4, master mp4, report) to the ALREADY RUNNING local bridge mailbox (127.0.0.1 only, no tunnel touched, no token printed, nothing published). Large files go in
64 MB parts with an upload id (the mailbox's documented protocol, as tools/remake_deliver.py). For each file the server's SHA-256 and size are compared with the local file and the stored bytes
are re-read. Writes projects/fusion_finale_20261029/livraison/mailbox_delivery.json (file ids, sizes, hashes, absolute Windows paths)."""
import hashlib, json, shutil, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; BASE = ROOT / 'projects' / 'fusion_finale_20261029'; OUT = BASE / 'livraison'; OUT.mkdir(exist_ok=True)
NM = 'LA_DERNIERE_POMPE_partie1_FUSION'
pairs = [(BASE / 'film' / 'leger.mp4', f'{NM}_leger_540x960.mp4'), (BASE / 'film' / 'report.json', f'{NM}_rapport.json')]
if '--no-master' not in sys.argv: pairs.insert(0, (BASE / 'film' / 'master.mp4', f'{NM}_master_1080x1920.mp4'))
files = []
for src, dst in pairs:
    if not (OUT / dst).exists() or (OUT / dst).stat().st_size != src.stat().st_size: shutil.copyfile(src, OUT / dst)
    files.append(OUT / dst)
state = Path.home() / '.claude-code-bridge'
cfg = json.loads((state / 'config.json').read_text(encoding='utf-8-sig')).get('cloud_mailbox') or {}
assert cfg.get('enabled') is True, 'boîte aux lettres désactivée'
base = f"http://127.0.0.1:{int(cfg.get('port', 18765))}"; H = {'Authorization': 'Bearer ' + (state / 'mailbox' / 'token').read_text(encoding='utf-8').strip()}
with urllib.request.urlopen(urllib.request.Request(base + '/v1/ping', headers=H), timeout=10) as r: assert json.load(r)['ok']
rec = {}
for p in files:
    data = p.read_bytes(); dg = hashlib.sha256(data).hexdigest(); mime = {'.mp4': 'video/mp4', '.json': 'application/json'}[p.suffix]; CH = 64 * 1048576
    if len(data) <= 90 * 1048576:
        req = urllib.request.Request(base + '/v1/files?name=' + urllib.parse.quote(p.name), data=data, headers=dict(H, **{'Content-Type': mime}), method='POST')
        with urllib.request.urlopen(req, timeout=3600) as r: meta = json.load(r)
    else:
        uid = 'fus-' + dg[:24]; off = 0
        while off < len(data):
            part = data[off:off + CH]; last = off + len(part) >= len(data)
            url = f"{base}/v1/files?name={urllib.parse.quote(p.name)}&upload_id={uid}&offset={off}" + ('&final=1' if last else '')
            req = urllib.request.Request(url, data=part, headers=dict(H, **{'Content-Type': mime}), method='POST')
            with urllib.request.urlopen(req, timeout=3600) as r: meta = json.load(r)
            off += len(part)
    assert meta['ok'] and meta['sha256'] == dg and meta['bytes'] == len(data), "le serveur n'a pas confirmé la même empreinte"
    stored = state / 'mailbox' / 'files' / f"{meta['file_id']}.bin"; back = hashlib.sha256(stored.read_bytes()).hexdigest() if stored.exists() else None
    rec[p.name] = dict(file_id=meta['file_id'], bytes=meta['bytes'], sha256=dg, local_path=str(p.resolve()), stored_bytes_sha256_ok=(back == dg) if back else 'non relu')
    print(p.name, meta['file_id'], meta['bytes'], 'octets ; empreinte confirmée ; relue sur disque :', 'OK' if back == dg else back, flush=True)
(OUT / 'mailbox_delivery.json').write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
