"""Send the verified « La marche » MP4 to the ALREADY RUNNING local bridge mailbox (127.0.0.1 only).
No tunnel is created, no token is printed, nothing is made public. A signed download link is then requested by the
orchestrator (bridge_cloud_file) with the returned file id."""
import hashlib, json, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / 'projects' / 'la_marche_20261028'
state = Path.home() / '.claude-code-bridge'
cfg = json.loads((state / 'config.json').read_text(encoding='utf-8-sig')).get('cloud_mailbox') or {}
assert cfg.get('enabled') is True, 'boîte aux lettres désactivée'
base = f"http://127.0.0.1:{int(cfg.get('port', 18765))}"
H = {'Authorization': 'Bearer ' + (state / 'mailbox' / 'token').read_text(encoding='utf-8').strip()}
with urllib.request.urlopen(urllib.request.Request(base + '/v1/ping', headers=H), timeout=10) as r: assert json.load(r)['ok']
rec = {}
for name, mime in (('la_marche_720x1280_24fps.mp4', 'video/mp4'),):
    p = OUT / name; data = p.read_bytes(); dg = hashlib.sha256(data).hexdigest()
    ver = json.loads((OUT / 'verification' / 'verification.json').read_text(encoding='utf-8'))
    assert ver['sha256'] == dg and ver['mediacheck']['ok'], 'fichier modifié depuis la vérification'
    req = urllib.request.Request(base + '/v1/files?name=' + urllib.parse.quote(name), data=data, headers=dict(H, **{'Content-Type': mime}), method='POST')
    with urllib.request.urlopen(req, timeout=900) as r: meta = json.load(r)
    assert meta['ok'] and meta['sha256'] == dg and meta['bytes'] == len(data)
    rec[name] = {k: meta[k] for k in ('file_id', 'name', 'bytes', 'sha256')}
    print(name, meta['file_id'], meta['bytes'], 'octets, empreinte vérifiée')
(OUT / 'mailbox_delivery.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')
