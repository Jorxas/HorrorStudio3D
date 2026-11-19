"""python -m hstudio.histoire <étape> <dossier> [options]   — le kit de production d'une histoire narrée.

Étapes, dans l'ordre (guide : docs/GUIDE_HISTOIRE_POUR_IA.md) :
  nouveau     crée le dossier type : script.txt (modèle), histoire.py (modèle commenté), voix.json, dossiers
  voix        DEVIS en caractères (rien n'est envoyé) ; --oui génère (après accord) ; --importer F.mp3 reprend une voix
  phrases     alignement de la voix -> voix/lignes.json + PHRASES.md (numéro, début, fin de chaque phrase)
  construire  exécute histoire.py -> construit/ (film long 16:9, vertical complet, Shorts PARTIE N, bruitages)
  apercu      planches basse définition de chaque cadrage, dans les deux formats (+ alertes mesurées)
  verifier    contrôles sans rendu + contrôle de scène du moteur (tools/verifier_scene.py)
  rendre      image des versions -> rendus/ (PS1 : CPU, 6 processus ; VOXEL : GPU, un seul rendu à la fois)
  mixer       voix + bruitages + ambiances -> mix/ à -14 LUFS, crête ≤ -1 dBTP, mesurés
  livrer      LIVRAISON/ : films, copies légères < 30 Mo, mesures, planches finales, PDF de publication
  etat        où en est le dossier, et l'étape suivante
  planifier   vidéos prévues à l'avance (Desktop\\videpgene\\PLANNING : script + miniature + date) ; --ajouter, --produire, --terminer
  catalogue  ce que le moteur sait faire : --lieux, --lieu NOM, --personnages, --gestes, --expressions, --objets, --sons"""
import argparse
import os
import sys

from .common import KitError, Story, read_json, write_json, ENGINE

STAGES = ('nouveau', 'voix', 'phrases', 'construire', 'apercu', 'verifier', 'rendre', 'mixer', 'livrer', 'etat', 'planifier', 'catalogue')
MODELES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modeles')


def say(*a, **k):
    print(*a, flush=True)


def nouveau(folder, titre=None):
    st = Story(folder)
    for d in (st.dir, st.voix, st.construit, st.planches, st.rendus, st.mix, st.livraison): os.makedirs(d, exist_ok=True)
    made = []
    for src, dst in (('script.txt', st.script), ('histoire.py', st.histoire), ('LISEZMOI.txt', st.readme)):
        if os.path.exists(dst): say(f'(gardé tel quel : {dst})'); continue
        txt = open(os.path.join(MODELES, src), encoding='utf-8').read()
        txt = txt.replace('{{DOSSIER}}', st.dir).replace('{{MOTEUR}}', ENGINE)
        if titre: txt = txt.replace("TITRE = 'MON TITRE'", f'TITRE = {titre!r}')
        with open(dst, 'w', encoding='utf-8') as f: f.write(txt)
        made.append(dst)
    if not os.path.exists(st.voix_json):
        from .voix import DEFAULTS
        write_json(st.voix_json, DEFAULTS); made.append(st.voix_json)
    for m in made: say('créé : ' + m)
    say(f'Dossier prêt : {st.dir}\nÉtape suivante : écris script.txt (balises ElevenLabs, « # rythme », « # coupe »), puis :\n'
        f'  python -m hstudio.histoire voix "{st.dir}"        (devis, rien n\'est envoyé)')


def etat(folder):
    st = Story(folder)
    if not os.path.isdir(st.dir): raise KitError(f'dossier introuvable : {st.dir} (étape nouveau)')
    nxt = None
    def row(ok, label, detail=''):
        nonlocal nxt
        say(f"{'✓' if ok else '·'} {label}{('  — ' + detail) if detail else ''}")
    from . import script as SC
    has_script = os.path.exists(st.script)
    if has_script:
        try:
            sc = SC.parse(st.script); row(True, 'script.txt', f"{len(sc['phrases'])} phrases, {len(sc['parts'])} parties de voix, {sum(1 for p in sc['phrases'] if p['coupe'])} « # coupe »")
        except KitError as e: row(False, 'script.txt', str(e))
    else: row(False, 'script.txt'); nxt = nxt or 'nouveau'
    if os.path.exists(st.voice):
        from .common import duration
        row(True, 'voix/voix.mp3', f'{duration(st.voice):.1f} s' + ('' if os.path.exists(st.alignment) else ' (sans alignement : calage sur les silences)'))
    else: row(False, 'voix/voix.mp3', 'devis : étape voix'); nxt = nxt or 'voix'
    if os.path.exists(st.lignes): row(True, 'voix/lignes.json + PHRASES.md', f'{len(read_json(st.lignes))} phrases')
    else: row(False, 'voix/lignes.json'); nxt = nxt or 'phrases'
    row(os.path.exists(st.histoire), 'histoire.py')
    dec = read_json(st.decoupe) if os.path.exists(st.decoupe) else None
    if dec:
        row(True, 'construit/', ', '.join(f"{v['id']} {v['dur']:.0f} s" for v in dec['versions']))
        if os.path.exists(st.histoire) and os.path.getmtime(st.histoire) > os.path.getmtime(st.decoupe): say('  ! histoire.py a changé depuis : les étapes suivantes reconstruisent d\'elles-mêmes')
    else: row(False, 'construit/', 'étape construire (puis apercu)'); nxt = nxt or 'construire'
    ap = [f for f in os.listdir(st.planches) if f.startswith('apercu_') and f.endswith('.jpg')] if os.path.isdir(st.planches) else []
    row(bool(ap), 'planches d\'aperçu', f'{len(ap)} planches'); nxt = nxt or (None if ap else 'apercu')
    vv = [v for v in (dec or {}).get('versions', []) if v['id'] != 'complet_9x16']
    for v in vv:
        from .common import version_hash
        stamp = st.video_only(v['id']).replace('.mp4', '.json')
        r = os.path.exists(st.video_only(v['id'])) and os.path.exists(stamp) and os.path.isdir(st.version_dir(v['id']))             and read_json(stamp).get('episode_sha1') == version_hash(st.version_dir(v['id'])) and not read_json(stamp).get('secondes')
        m = os.path.exists(st.mix_wav(v['id']))
        row(r and m, f"{v['id']}", f"image {'✓' if r else 'à rendre (absente, partielle ou d’une autre mise en scène)'}, son {'✓' if m else 'à mixer'}")
        if not r: nxt = nxt or 'rendre'
        if not m: nxt = nxt or 'mixer'
    rep = os.path.join(st.livraison, 'RAPPORT_MESURES.md')
    row(os.path.exists(rep), 'LIVRAISON/RAPPORT_MESURES.md'); nxt = nxt or (None if os.path.exists(rep) else 'livrer')
    say(f"Étape suivante : {nxt or 'rien — regarde les planches finales et le rapport, puis donne les fichiers au propriétaire'}")


def catalogue(a):
    sys.path.insert(0, ENGINE)
    show_all = not any((a.lieux, a.lieu, a.personnages, a.gestes, a.expressions, a.objets, a.sons))
    if a.lieu:
        from hstudio.engines.pixel3d import sets as SE
        st = SE.make_set(a.lieu, {'type': a.lieu})
        say(f'Lieu « {a.lieu} » : repères (x, z) — x vers la droite de l\'image en regardant vers +z')
        for k, v in sorted(st.anchors.items(), key=lambda kv: (kv[1][1], kv[1][0]) if isinstance(kv[1], (list, tuple)) else (0, 0)):
            say(f'  {k:<28s} {v}')
        say('Détails des grands lieux : docs/FORMAT_EPISODE.md (hotel_nuit § 10, theatre_bal, etage_zero, apartment).')
        return
    if a.lieux or show_all:
        from hstudio.engines.pixel3d import places as PL
        say('LIEUX ({"type": NOM}) : grands lieux dirigés : hotel_nuit (Chambre 313), theatre_bal, pompe_station, etage_zero, apartment')
        say('  lieux prêts : ' + ', '.join(sorted(PL.PLACES)))
    if a.personnages or show_all:
        from hstudio.engines.pixel3d import hotel_cast as HC, creatures as CR
        chars = sorted(f[:-5] for f in os.listdir(os.path.join(ENGINE, 'library', 'characters')) if f.endswith('.json'))
        say('PERSONNAGES : bibliothèque (cast {"id": "@nom"}) : ' + ', '.join(chars))
        say('  préréglages de l\'hôtel ({"preset": NOM}) : ' + ', '.join(sorted(HC.PRESETS)))
        say('  types ({"kind": NOM}) : ' + ', '.join(sorted(CR.PRESETS)) + ' ; animaux : ' + ', '.join(sorted(CR.ANIMALS)))
    if a.gestes or show_all:
        from hstudio.acting import gestures as G
        say('GESTES (gesture) : ' + ', '.join(sorted(G.GESTURES)))
    if a.expressions or show_all:
        from hstudio.engines.pixel3d import assets as A
        say('EXPRESSIONS (face) : ' + ', '.join(A.FACE_KINDS))
    if a.objets or show_all:
        from hstudio.engines.pixel3d import poses as P, hotel_cast
        hotel_cast.register()                                   # adds crowbar, handset, mobile... (idempotent)
        from hstudio.engines.pixel3d import sets as _S, objets as OD            # objets détaillés `od_*` (enregistrés à l'import de sets), lots compris
        say('OBJETS TENUS (hold) : ' + ', '.join(i for i in P.HOLD_ITEMS if not i.startswith('od_')) + ' ; costumes : flute, flute_pair, wine_glass, bouquet, fan, letter')
        say('OBJETS TENUS DÉTAILLÉS (hold, PS1 + VOXEL) : ' + ', '.join(f'{k} ({v})' for k, v in OD.HELD_LABELS.items()))
        say('OBJETS POSÉS DÉTAILLÉS (props / objets de plan) : ' + ', '.join(f'{k} ({v})' for k, v in OD.LABELS.items()) + " ; réglages : docs/FORMAT_EPISODE.md « Objets détaillés »")
    if a.sons or show_all:
        from hstudio.audio import fabriques as FB, synth as S
        from . import mixage as MX
        say('SONS FABRIQUÉS (à nous, hstudio/audio/fabriques.py) :')
        for k, v in FB.SOUNDS.items(): say(f"  {k:<16s} {'nappe (dur=…)' if v['kind'] == 'bed' else 'ponctuel':<14s} {v['desc']}")
        say('  anciens noms acceptés : ' + ', '.join(f'{k} → {v}' for k, v in FB.ALIASES.items()))
        say('VRAIS BRUITAGES (library/audio_real) : ' + ', '.join(sorted(MX.library().keys())))
        say('SYNTHÈSE DU MOTEUR : ' + ', '.join(sorted(S.SFX)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m hstudio.histoire', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('etape', choices=STAGES)
    ap.add_argument('dossier', nargs='?')
    ap.add_argument('--titre'); ap.add_argument('--oui', action='store_true', help='voix : génère vraiment (payant, après accord)')
    ap.add_argument('--refaire', action='store_true'); ap.add_argument('--importer'); ap.add_argument('--alignement'); ap.add_argument('--jusqua', type=float)
    ap.add_argument('--format', default='tous'); ap.add_argument('--plans'); ap.add_argument('--chaque', type=float)
    ap.add_argument('--workers', type=int, default=6); ap.add_argument('--secondes', type=float)
    ap.add_argument('--habille', action='store_true', help='apercu VOXEL : images avec l\'habillage final (titre, sous-titres, messages, choix)')      # 9/11/2026
    ap.add_argument('--sans-leger', action='store_true'); ap.add_argument('--sans-pdf', action='store_true'); ap.add_argument('--sans-scene', action='store_true'); ap.add_argument('--images', action='store_true'); ap.add_argument('--forcer', action='store_true')
    for f in ('lieux', 'personnages', 'gestes', 'expressions', 'objets', 'sons'): ap.add_argument('--' + f, action='store_true')
    ap.add_argument('--lieu')
    ap.add_argument('--ajouter', metavar='TITRE', help='planifier : prévoit une nouvelle vidéo'); ap.add_argument('--date', help='planifier : AAAA-MM-JJ')
    ap.add_argument('--produire', action='store_true', help='planifier : ouvre la production de la prochaine vidéo prête (ou de NOM)')
    ap.add_argument('--terminer', action='store_true', help='planifier : marque NOM comme terminée')
    a = ap.parse_args(argv)
    try:
        if a.etape == 'catalogue': catalogue(a); return 0
        if a.etape == 'planifier':
            from . import planning as PL; PL.run(a, say); return 0
        if not a.dossier: raise KitError('indique le dossier de l\'histoire (chemin complet)')
        if a.etape == 'nouveau': nouveau(a.dossier, a.titre)
        elif a.etape == 'etat': etat(a.dossier)
        elif a.etape == 'voix':
            from . import voix as V
            if a.importer: V.import_voice(a.dossier, a.importer, a.alignement, a.jusqua, say)
            elif a.oui: V.generate(a.dossier, a.refaire, say)
            else: V.quote(a.dossier, say)
        elif a.etape == 'phrases':
            from . import phrases as PH; PH.build(a.dossier, say)
        elif a.etape == 'construire':
            from . import projet as PJ; PJ.build(a.dossier, say)
        elif a.etape == 'apercu':
            from . import apercu as AP; AP.make(a.dossier, a.format, a.plans, a.chaque, say, a.workers, habille=a.habille)
        elif a.etape == 'verifier':
            from . import verif as VF; VF.check(a.dossier, not a.sans_scene, a.images, say)
        elif a.etape == 'rendre':
            from . import rendu as RD; RD.render(a.dossier, a.format, a.workers, a.secondes, a.forcer, say)
        elif a.etape == 'mixer':
            from . import mixage as MX; MX.mix(a.dossier, say)
        elif a.etape == 'livrer':
            from . import livraison as LV; LV.deliver(a.dossier, not a.sans_leger, not a.sans_pdf, say)
        return 0
    except KitError as e:
        say('ERREUR : ' + str(e)); return 1


if __name__ == '__main__':
    sys.exit(main())
