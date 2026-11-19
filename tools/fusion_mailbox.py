"""python tools/fusion_mailbox.py FILE [FILE ...]  -> upload to the ALREADY RUNNING local bridge mailbox (127.0.0.1 only).
No tunnel is created or touched, no token is printed, nothing is published. The stored bytes are then re-read from the mailbox
folder and their SHA-256 compared with the local file. A signed download link is requested by the orchestrator (bridge_cloud_file)
with the returned file id. Writes projects/fusion_20261029/mailbox_delivery.json."""
import hashlib, json, mimetypes, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / 'projects' / 'fusion_20261029'
state = Path.home() / '.claude-code-bridge'
cfg = json.loads((state / 'config.json').read_text(encoding='utf-8-sig')).get('cloud_mailbox') or {}
assert cfg.get('enabled') is True, 'boîte aux lettres désactivée'
base = f"http://127.0.0.1:{int(cfg.get('port', 18765))}"
H = {'Authorization': 'Bearer ' + (state / 'mailbox' / 'token').read_text(encoding='utf-8').strip()}
with urllib.request.urlopen(urllib.request.Request(base + '/v1/ping', headers=H), timeout=10) as r: assert json.load(r)['ok']
dst = OUT / 'mailbox_delivery.json'; rec = json.loads(dst.read_text(encoding='utf-8')) if dst.exists() else {}
for f in sys.argv[1:]:
    p = Path(f); data = p.read_bytes(); dg = hashlib.sha256(data).hexdigest(); mime = {'.mp4': 'video/mp4', '.html': 'text/html', '.zip': 'application/zip'}.get(p.suffix, mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
    req = urllib.request.Request(base + '/v1/files?name=' + urllib.parse.quote(p.name), data=data, headers=dict(H, **{'Content-Type': mime}), method='POST')
    with urllib.request.urlopen(req, timeout=1800) as r: meta = json.load(r)
    assert meta['ok'] and meta['sha256'] == dg and meta['bytes'] == len(data), 'le serveur n\'a pas confirmé la même empreinte'
    stored = state / 'mailbox' / 'files' / f"{meta['file_id']}.bin"
    back = hashlib.sha256(stored.read_bytes()).hexdigest() if stored.exists() else None
    rec[p.name] = dict(file_id=meta['file_id'], bytes=meta['bytes'], sha256=dg, local_path=str(p.resolve()), stored_bytes_sha256_ok=(back == dg) if back else 'non relu')
    print(p.name, meta['file_id'], meta['bytes'], 'octets, empreinte confirmée par le serveur;', 'relue sur disque : ' + ('OK' if back == dg else str(back)))
dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
