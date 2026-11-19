"""Transfer only the verified demo artifacts to the ALREADY RUNNING bridge mailbox.

No tunnel creation, no messages to another assistant, no token in arguments or output.
Run after si_demo_muet.py has produced verification.json. Download links are then
requested through bridge_cloud_file using the returned real file IDs.
"""
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'projects' / 'demo_muet_20261028'


def main():
    state = Path.home() / '.claude-code-bridge'
    config = json.loads((state/'config.json').read_text(encoding='utf-8-sig'))
    settings = config.get('cloud_mailbox') or {}
    if settings.get('enabled') is not True:
        raise RuntimeError('Boîte aux lettres désactivée : aucun transfert.')
    base = f"http://127.0.0.1:{int(settings.get('port',18765))}"
    token = (state/'mailbox'/'token').read_text(encoding='utf-8').strip()
    headers = {'Authorization': 'Bearer '+token}
    request = urllib.request.Request(base+'/v1/ping',headers=headers)
    with urllib.request.urlopen(request,timeout=10) as response:
        assert json.load(response)['ok']
    verified = json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
    record_path = OUT/'mailbox_delivery.json'
    records = json.loads(record_path.read_text(encoding='utf-8')) if record_path.exists() else {}
    for kind in ('mobile','master','captures'):
        if kind == 'captures':
            path, mime = OUT/'captures_timecodes.png', 'image/png'
        else:
            item = verified[kind]
            assert item['integrity']['ok'] and item['integrity']['decoded']
            path, mime = Path(item['path']), 'video/mp4'
        assert path.resolve().parent == OUT.resolve()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if kind != 'captures':
            assert digest == verified[kind]['sha256'], 'Fichier modifié après vérification'
        if kind in records and records[kind]['sha256'] == digest:
            print(kind, records[kind]['file_id'], '(déjà transféré)')
            continue
        request = urllib.request.Request(base+'/v1/files?name='+urllib.parse.quote(path.name),
            data=data,headers=dict(headers,**{'Content-Type':mime}),method='POST')
        with urllib.request.urlopen(request,timeout=120) as response:
            meta = json.load(response)
        assert meta['ok'] and meta['sha256']==digest and meta['bytes']==len(data)
        records[kind] = {k:meta[k] for k in ('file_id','name','bytes','sha256')}
        record_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(kind,meta['file_id'],meta['bytes'],'octets : empreinte vérifiée')


if __name__ == '__main__':
    main()
