"""python tools/remake_deliver.py  -> gathers the delivered files of the two remakes under projects/remakes_voxelgpu_20261029/livraison/ and uploads them to the
ALREADY RUNNING local bridge mailbox (127.0.0.1 only; no tunnel is created or touched, no token is printed, nothing is published).

For each file the server's SHA-256 and byte count are compared with the local file and the stored bytes are re-read from the mailbox folder. Writes
livraison/mailbox_delivery.json (file ids, sizes, hashes, absolute Windows paths). Files: for each film the master, the light MP4, the report and the
comparison page (zipped with its two videos and sheets). The source videos are not re-delivered (they came from the mailbox)."""
import hashlib, json, shutil, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; BASE = ROOT / 'projects' / 'remakes_voxelgpu_20261029'; OUT = BASE / 'livraison'; OUT.mkdir(exist_ok=True)
NAMES = {'pompe': 'LA_DERNIERE_POMPE_partie1_REMAKE_VOXELGPU', 'sol': 'NE_TOUCHE_PAS_LE_SOL_partie4_REMAKE_VOXELGPU'}
files = []
for film, nm in NAMES.items():
    d = BASE / film
    for src, dst in ((d / 'master.mp4', f'{nm}_master_1080x1920.mp4'), (d / 'leger.mp4', f'{nm}_leger_540x960.mp4'), (d / 'report.json', f'{nm}_rapport.json')):
        shutil.copyfile(src, OUT / dst); files.append(OUT / dst)
    z = OUT / f'{nm}_comparaison.zip'
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED) as zf:
        for f in sorted((d / 'comparaison').iterdir()): zf.write(f, f.name)
    files.append(z)
state = Path.home() / '.claude-code-bridge'
cfg = json.loads((state / 'config.json').read_text(encoding='utf-8-sig')).get('cloud_mailbox') or {}
assert cfg.get('enabled') is True, 'boîte aux lettres désactivée'
base = f"http://127.0.0.1:{int(cfg.get('port', 18765))}"; H = {'Authorization': 'Bearer ' + (state / 'mailbox' / 'token').read_text(encoding='utf-8').strip()}
with urllib.request.urlopen(urllib.request.Request(base + '/v1/ping', headers=H), timeout=10) as r: assert json.load(r)['ok']
dst = OUT / 'mailbox_delivery.json'; rec = {}
for p in files:
    data = p.read_bytes(); dg = hashlib.sha256(data).hexdigest(); mime = {'.mp4': 'video/mp4', '.json': 'application/json', '.zip': 'application/zip'}[p.suffix]
    CH = 64 * 1048576
    if len(data) <= 90 * 1048576:                       # one request (the mailbox accepts up to ~95 MB at once)
        req = urllib.request.Request(base + '/v1/files?name=' + urllib.parse.quote(p.name), data=data, headers=dict(H, **{'Content-Type': mime}), method='POST')
        with urllib.request.urlopen(req, timeout=3600) as r: meta = json.load(r)
    else:                                               # parts of 64 MB with an upload id, `final=1` on the last (the mailbox's documented protocol)
        uid = 'rmk-' + dg[:24]; off = 0
        while off < len(data):
            part = data[off:off + CH]; last = off + len(part) >= len(data)
            url = f"{base}/v1/files?name={urllib.parse.quote(p.name)}&upload_id={uid}&offset={off}" + ('&final=1' if last else '')
            req = urllib.request.Request(url, data=part, headers=dict(H, **{'Content-Type': mime}), method='POST')
            with urllib.request.urlopen(req, timeout=3600) as r: meta = json.load(r)
            off += len(part)
    assert meta['ok'] and meta['sha256'] == dg and meta['bytes'] == len(data), "le serveur n'a pas confirmé la même empreinte"
    stored = state / 'mailbox' / 'files' / f"{meta['file_id']}.bin"; back = hashlib.sha256(stored.read_bytes()).hexdigest() if stored.exists() else None
    rec[p.name] = dict(file_id=meta['file_id'], bytes=meta['bytes'], sha256=dg, local_path=str(p.resolve()), stored_bytes_sha256_ok=(back == dg) if back else 'non relu')
    print(p.name, meta['file_id'], meta['bytes'], 'octets ; empreinte confirmée ; relue sur disque :', 'OK' if back == dg else back)
dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
print('écrit', dst)
