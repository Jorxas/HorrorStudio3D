"""python tools/export_commercial.py [--strip] [--write]

Passe en revue les banques de modèles importés (voxelgpu_js/assets_vox/*/CREDITS.json) :
  * `commercial_ok` faux (usage perso seulement) -> avec --strip, la banque est RETIRÉE du dossier (et du catalogue au prochain `python -m hstudio.catalogue build`) ;
  * `credit_required` vrai (CC BY) -> le texte de crédit à mettre dans la description des vidéos ; --write l'enregistre dans CREDITS_A_PUBLIER.txt ;
  * le reste (CC0, créé pour ce studio) : rien à faire.
Ne touche à rien sans --strip. Couvre aussi les banques sonores de library/audio_real (CC BY d'Oculus : crédit exigé)."""
import argparse, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BANKS = ROOT / 'voxelgpu_js' / 'assets_vox'
SOUNDS = ROOT / 'library' / 'audio_real'                 # banques de vrais sons (tools/sfx_bank_import.py)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--strip', action='store_true'); ap.add_argument('--write', action='store_true'); a = ap.parse_args()
    rows, credits, personal = [], [], []
    for b in sorted(BANKS.glob('*')):
        if not b.is_dir(): continue
        try: c = json.loads((b / 'CREDITS.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): c = {'license': '? (CREDITS.json absent)', 'commercial_ok': False}
        n = len(list(b.glob('*.vox'))); ok = bool(c.get('commercial_ok', True)); by = bool(c.get('credit_required', False))
        rows.append((b.name, n, c.get('license', '?'), 'oui' if ok else 'NON', 'OUI' if by else 'non'))
        if by: credits.append(c.get('credit_text') or f"{c.get('name', b.name)} — {c.get('author', '?')} — {c.get('license', '?')}")
        if not ok: personal.append(b)
    print(f"{'banque':<18}{'modèles':>8}  {'licence':<34}{'vente ok':<10}crédit exigé")
    for r in rows: print(f'{r[0]:<18}{r[1]:>8}  {r[2][:32]:<34}{r[3]:<10}{r[4]}')
    print('\nÀ METTRE DANS LA DESCRIPTION de toute vidéo qui utilise ces modèles :' if credits else '\nAucun crédit exigé.')
    for c in credits: print('  •', c)
    if personal: print('\nUSAGE PERSONNEL SEULEMENT (à retirer avant de vendre) :', ', '.join(b.name for b in personal))
    # ---- banques sonores : library/audio_real/banks/*/CREDITS.json
    srows, spersonal, scredits = [], [], []
    for f in sorted((SOUNDS / 'banks').glob('*/CREDITS.json')):
        try: c = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        ok = bool(c.get('commercial_ok', True)); by = bool(c.get('credit_required', False)); srows.append((f.parent.name, c.get('files', '?'), c.get('license', '?'), 'oui' if ok else 'NON', 'OUI' if by else 'non'))
        if by and c.get('credit_text'): scredits.append(c['credit_text']); credits.append(c['credit_text'])
        if not ok: spersonal.append(f.parent.name)
    if srows:
        print(f"\n{'banque sonore':<18}{'sons':>8}  {'licence':<34}{'vente ok':<10}crédit exigé")
        for r in srows: print(f'{r[0]:<18}{r[1]!s:>8}  {r[2][:32]:<34}{r[3]:<10}{r[4]}')
        if scredits:
            print('\nÀ METTRE DANS LA DESCRIPTION de toute vidéo qui utilise ces sons :')
            for c in scredits: print('  •', c)
        if spersonal: print('\nSONS USAGE PERSONNEL SEULEMENT (à retirer avant de vendre) :', ', '.join(spersonal))
    if a.strip and spersonal:                                    # retire les variantes de ces banques du manifeste et leurs fichiers
        mp = SOUNDS / 'manifest.json'; man = json.loads(mp.read_text(encoding='utf-8'))
        for ev, e in list(man['events'].items()):
            keep = []
            for v in e['variants']:
                if (v.get('credit') or {}).get('bank') in spersonal: (SOUNDS / v['file']).unlink(missing_ok=True)
                else: keep.append(v)
            if keep: e['variants'] = keep
            else: del man['events'][ev]
        mp.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding='utf-8')
        for b in spersonal: shutil.rmtree(SOUNDS / 'banks' / b, ignore_errors=True); print('sons retirés :', b)
    if a.write: (ROOT / 'CREDITS_A_PUBLIER.txt').write_text('\n'.join(credits) + '\n', encoding='utf-8'); print('écrit : CREDITS_A_PUBLIER.txt')
    if a.strip:
        for b in personal: shutil.rmtree(b); print('retiré :', b.name)
        if not personal: print('rien à retirer')


if __name__ == '__main__': main()
