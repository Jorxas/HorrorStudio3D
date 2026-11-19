"""Enregistre les personnages en costume XVIIIe dans la bibliothèque du moteur (`library/characters/<id>.json`).

    python tools/costume_library.py            écrit / met à jour les fiches (idempotent : même contenu -> fichier inchangé)
    python tools/costume_library.py --check    dit seulement ce qui changerait

Chaque fiche porte `"costume": "<préréglage>"` (la définition vit dans hstudio/engines/pixel3d/costumes.py, une seule source) et un
look de repli en clés ordinaires (outfit, couleurs, coiffure) pour les styles qui ne lisent pas encore `costume` (CONSOLE 2D).
Dans un épisode : "cast": {"angelica": "@angelica"} ou {"angelica": {"ref": "angelica"}}.
"""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.engines.pixel3d import costumes as COS

LIB = ROOT / 'library' / 'characters'
NAMES = {'angelica': 'Angelica', 'eliza': 'Eliza (mariée)', 'eliza_souvenir': 'Eliza (souvenir, sans voile)', 'peggy': 'Peggy', 'hamilton': 'Hamilton',
         'laurens': 'Laurens', 'lafayette': 'Lafayette', 'washington': 'Washington', 'homme_chauve_rouge': 'Danseur en habit rouge'}
NOTES = {'angelica': "Robe de bal bronze/cuivre, plastron champagne à boutons, devant de jupe clair, grande chevelure bouclée noire, boucles d'oreilles dorées. Flûte de champagne levée au toast.",
         'eliza': "La mariée : robe turquoise, manches au coude à volants, chignon sous un voile long semé de pois et une couronne de fleurs blanches et bleu ciel, bouquet blanc.",
         'eliza_souvenir': "Eliza pendant le souvenir : même robe, sans voile, longue queue de cheval sur l'épaule droite.",
         'peggy': "Robe jaune paille, ceinture dorée, boucles relevées en chignon, flûte de champagne.",
         'hamilton': "Redingote bleu nuit à col et revers crème, boutons dorés par paires, gilet crème, jabot blanc, culotte crème, bottes hautes ; cheveux noirs en catogan, bouc et moustache.",
         'laurens': "Redingote bleu nuit à revers crème, gilet crème, jabot ; cheveux bruns en petite queue ; une flûte dans chaque main.",
         'lafayette': "Redingote bleu roi à revers blancs, barbe courte, houppe bouclée relevée.",
         'washington': "Le plus grand : longue redingote bleu nuit presque noire, épaulettes dorées à franges, gilet chamois, crâne rasé.",
         'homme_chauve_rouge': "Habit rouge écarlate à revers bleu nuit, culotte blanche, bottes noires, crâne rasé."}


def fallback_look(cs):
    """clés ordinaires pour les styles qui ne connaissent pas `costume` (approximation, pas le costume)"""
    hs = {'big_curls': 'curly', 'updo': 'bun', 'updo_curls': 'bun', 'side_ponytail': 'ponytail', 'queue': 'ponytail', 'short': 'short', 'shaved': 'bald', 'puff': 'curly', 'afro_crown': 'curly'}[cs['hair']]
    lk = dict(skin=list(cs['skin']), hair=list(cs['hair_color']), hair_style=hs, headphones=False, backpack=False)
    if cs['type'] == 'gown': lk.update(outfit='dress', hood=list(cs['bodice']), jeans=list(cs['skirt']))
    else: lk.update(outfit='coat', hood=list(cs['coat']), jeans=list(cs['breeches']))
    if cs.get('beard'): lk['beard'] = {'goatee': 'mustache', 'short_full': True, 'mustache': 'mustache', 'stubble': 'stubble'}[cs['beard']]
    return lk


def entry(cid):
    cs = COS.spec_of({'costume': cid}); main = cid in COS.PRINCIPAUX
    name = NAMES.get(cid) or cid.replace('_', ' ').capitalize()
    look = dict(fallback_look(cs), costume=cid)
    if cs.get('scale'): look['scale'] = cs['scale']
    note = (NOTES.get(cid) or ('Ensemble du bal XVIIIe : ' + COS.describe(cid) + '.')) + (' Tête peinte en pixels façon skin (face_skin) : sourcils, yeux, lèvres et barbe peints, yeux, sourcils et bouche animés.' if cs.get('face_skin') else '')
    return {'id': cid, 'name': name, 'look': look, 'voice': {'draft': 'woman' if cs['type'] == 'gown' else 'man', 'elevenlabs_voice_id': ''},
            'personality': {'expressive': .85 if main else .6, 'energy': .7, 'shy': .1}, 'relations': {}, 'group': 'bal_xviiie', 'notes': note}


def catalogue(planches):
    """fiches du catalogue (catalogue/extra.json, le point d'entrée prévu pour les modules) + miniatures VOXEL et PS1 tirées des planches
    « face / profil / dos » (vue de face recadrée) ; les autres fiches de extra.json sont gardées telles quelles"""
    from PIL import Image
    from hstudio.voxelgpu import b_costumes as BCO
    cat = ROOT / 'catalogue'; extra = cat / 'extra.json'
    try: old = json.loads(extra.read_text(encoding='utf-8'))
    except (OSError, ValueError): old = []
    keep = [e for e in old if not str(e.get('id', '')).startswith('costume/')]
    es = BCO.entries(); n = 0
    for e in es:
        e['styles'] = {'ps1': 'native', 'voxel': 'native'}
        for style, sub in (('voxel', 'thumbs'), ('ps1', 'thumbs_ps1')):
            src = Path(planches) / style / f"vues_{e['key']}.png"
            if not src.exists(): continue
            im = Image.open(src).convert('RGB'); w, h = im.size; th = im.crop((0, int(h * .12), w // 3 + 60, int(h * .86)))
            th = th.resize((320, 240) if False else (round(240 * th.width / th.height), 240), Image.LANCZOS)
            box = Image.new('RGB', (320, 240), (20, 20, 24)); box.paste(th, ((320 - th.width) // 2, 0))
            (cat / sub).mkdir(parents=True, exist_ok=True); box.save(cat / sub / (e['id'].replace('/', '_') + '.jpg'), quality=82); n += 1
    extra.write_text(json.dumps(keep + es, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'catalogue/extra.json : {len(es)} fiches de costumes ({len(keep)} autres gardées), {n} miniatures')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); ap.add_argument('--catalogue', default='')
    a = ap.parse_args()
    if a.catalogue: catalogue(a.catalogue); return
    LIB.mkdir(parents=True, exist_ok=True); n = 0
    for cid in COS.PRINCIPAUX + COS.ENSEMBLE_DAMES + COS.ENSEMBLE_HOMMES:
        p = LIB / f'{cid}.json'; txt = json.dumps(entry(cid), ensure_ascii=False, indent=1) + '\n'
        old = p.read_text(encoding='utf-8') if p.exists() else None
        if old is not None and not old.strip().startswith('{'): continue
        if old is not None and json.loads(old).get('group') != 'bal_xviiie':
            print(f'  {cid} : une fiche du même nom existe déjà (pas un personnage du bal), laissée telle quelle'); continue
        if old != txt:
            n += 1; print(('  changerait ' if a.check else '  écrit ') + str(p.relative_to(ROOT)))
            if not a.check: p.write_text(txt, encoding='utf-8')
    print(f'{n} fiche(s) {"à mettre à jour" if a.check else "écrites"} dans library/characters')


if __name__ == '__main__':
    main()
