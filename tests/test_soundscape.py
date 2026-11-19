"""Tests hors ligne de la mise en scene sonore narrative (aucun reseau, aucun ffmpeg, aucun cout).

    python tests/test_soundscape.py

Verifie le contrat de hstudio/audio/soundscape.py : detection des beats, determinisme, innocuite sur
les anciennes histoires, synchronisation A L'ECHANTILLON par le vrai chemin du mixeur, panoramique,
priorite de la narration (ducking), variete des espaces et absence de saturation.
"""
import copy, json, os, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hstudio.audio                                   # installe le provider de bruitages
from hstudio.audio import synth as S, library as L, mixer as MX, soundscape as SS

SR = S.SR
FAILS = []


def ok(name, cond, info=''):
    print(('  OK   ' if cond else '  FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: FAILS.append(name)


# ------------------------------------------------------------------ scene de test
SCRIPT = [
    "[tense] Tu avances dans le couloir.",          # 0
    "Puis la porte ouverte derriere lui.",          # 1  -> door_open
    "Tu ne dis rien.",                              # 2
    "Derriere vous, la creature se met a courir.",  # 3  -> threat_run
    "Tu attrapes ton double et le projettes.",       # 4  -> grab
    "La porte se referme.",                         # 5  -> door_close
    "Et soudain...",                                # 6
    "Plus aucun bruit.",                            # 7  -> dead_silence
    "Face a la creature.",                          # 8  -> threat_near
]

def scene(n=len(SCRIPT), step=2.0, talk=1.4):
    """repliques regulieres : 2 s par plan, 1.4 s de parole, donc 0.6 s de trou de narration"""
    lines = [{'start': i * step, 'end': i * step + talk} for i in range(n)]
    ep = {'style': 'pixel3d', 'seed': 7, 'intensity_start': .6,
          'shots': [{'lines': [i, i]} for i in range(n)]}
    spans = [(i * step, (i + 1) * step) for i in range(n)]
    return ep, lines, spans, n * step


# ------------------------------------------------------------------ 1. detection
def test_detect():
    print('1. detection des beats dans le script')
    b = SS.detect(SCRIPT)
    kinds = [x['kind'] for x in b]
    ok('les beats attendus sont trouves',
       kinds == ['door_open', 'threat_run', 'grab', 'door_close', 'dead_silence', 'threat_near'],
       ', '.join(kinds))
    ok('un beat est rattache a sa replique', [x['line'] for x in b] == [1, 3, 4, 5, 7, 8])
    ok('les accents ne changent rien',
       [x['kind'] for x in SS.detect(['La porte se référme.'])] == ['door_close'])
    ok('la casse ne change rien',
       [x['kind'] for x in SS.detect(['PLUS AUCUN BRUIT.'])] == ['dead_silence'])
    ok('une didascalie ne declenche pas de beat', not SS.detect(['[la porte se referme] Il parle.']))
    ok('une replique vide ne declenche rien', not SS.detect(['', None, '   ']))
    # cooldown : la meme situation sur trois repliques de suite ne rejoue pas trois fois
    ep, lines, spans, dur = scene()
    many = ["Face a la creature.", "Elle s'approche.", "Elle est tout pres.",
            "Elle s'approche encore.", "Tout pres.", "Elle s'approche.", "x", "y", "z"]
    p = SS.plan(ep, lines, spans, script=many)
    near = [x for x in p.beats if x['kind'] == 'threat_near']
    ok('cooldown : une menace qui se prolonge ne declenche pas a chaque replique',
       len(near) < 4, f'{len(near)} declenchements pour 6 repliques de menace')


# ------------------------------------------------------------------ 2. determinisme
def test_determinism():
    print('2. determinisme')
    ep, lines, spans, dur = scene()
    a = SS.plan(ep, lines, spans, script=SCRIPT)
    b = SS.plan(ep, lines, spans, script=SCRIPT)
    ok('deux plans identiques pour la meme entree', a.cues == b.cues and a.zones == b.zones)
    ok('le plan ne depend pas de l alea', json.dumps(a.cues) == json.dumps(b.cues))
    ja = json.dumps(a.apply(ep), sort_keys=True); jb = json.dumps(b.apply(ep), sort_keys=True)
    ok('deux episodes enrichis identiques', ja == jb)


# ------------------------------------------------------------------ 3. innocuite (anciennes histoires)
def test_integrity():
    print('3. innocuite : les anciennes histoires ne changent pas')
    ep, lines, spans, dur = scene()
    plain = ['Il marche.', 'Elle attend.', 'Rien ne bouge.'] + [''] * 6
    p = SS.plan(ep, lines, spans, script=plain)
    before = copy.deepcopy(ep)
    out = p.apply(ep)
    ok('un script sans beat ne pose aucun evenement', not p.cues, f'{len(p.cues)} cues')
    ok("l'episode source n'est jamais modifie sur place", ep == before)
    ok('sans beat, pas de silence force ni de tension imposee', not p.silences and not p.tension)

    # les valeurs ecrites a la main restent prioritaires
    ep2, lines2, spans2, _ = scene()
    ep2['ambience_gain'] = 1.0
    ep2['shots'][1]['sfx'] = [{'name': 'static', 'at': .1, 'gain': .4}]
    ep2['shots'][1].setdefault('audio', {})['ambience'] = 'rain'
    p2 = SS.plan(ep2, lines2, spans2, script=SCRIPT)
    out2 = p2.apply(ep2)
    ok('un ambience_gain ecrit a la main est respecte', out2['ambience_gain'] == 1.0)
    ok('les cues ecrites a la main sont conservees',
       any(c.get('name') == 'static' for c in out2['shots'][1]['sfx']))
    ok('le plan ajoute ses cues en plus, sans remplacer',
       len(out2['shots'][1]['sfx']) >= 1)

    # le module est purement opt-in : rien dans le studio ne l'appelle tout seul
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    users = []
    for d, _, fs in os.walk(os.path.join(root, 'hstudio')):
        for f in fs:
            if not f.endswith('.py') or f == 'soundscape.py': continue
            if 'soundscape' in open(os.path.join(d, f), encoding='utf-8', errors='ignore').read():
                users.append(os.path.relpath(os.path.join(d, f), root))
    ok('aucun module du studio n importe soundscape (donc aucun episode existant ne change)',
       not users, ', '.join(users))


# ------------------------------------------------------------------ 4. le vrai chemin du mixeur
def bus(ep, lines, spans, dur, seed=7):
    """hstudio/audio/mixer.py sfx_cues() sur un bus isole : pas de voix, pas de lit, pas de ffmpeg"""
    m = MX.Mixer.__new__(MX.Mixer)
    m.lines = lines; m.ep = ep; m.duration = dur; m.style = 'pixel3d'; m.wd = tempfile.mkdtemp()
    m.N = int((dur + 1.) * SR)
    m.voice = np.zeros(m.N, np.float32)
    m.L = np.zeros(m.N, np.float32); m.R = np.zeros(m.N, np.float32); m.REV = np.zeros(m.N, np.float32)
    S.reseed(seed)
    m.lib = L.LIB; L.LIB.seed = seed; L.LIB.used = {}; L.LIB.enabled = True
    m.sfx_cues(spans)
    return m


def test_sync():
    print("4. synchronisation : chaque evenement tombe a l'echantillon prevu")
    ep, lines, spans, dur = scene()
    p = SS.plan(ep, lines, spans, script=SCRIPT)
    ep_b = p.apply(ep)

    # a) le mixeur resout bien les cues relatives aux repliques au temps que le plan annonce
    m = MX.Mixer.__new__(MX.Mixer); m.lines = lines; m.ep = ep_b; m.duration = dur
    bad = []
    for k, shot in enumerate(ep_b['shots']):
        for cue in (shot.get('sfx') or []):
            t = m.cue_time(cue, spans[k][0])
            want = [c for c in p.cues if c['name'] == cue['name'] and abs(c['t'] - t) < 1e-6]
            if not want: bad.append((cue['name'], round(t, 4)))
    ok('le mixeur retrouve exactement les temps annonces par le plan', not bad, str(bad[:4]))

    # b) un evenement isole est pose a l'echantillon exact, au gain et au pan demandes
    c = [x for x in p.cues if x['name'] == 'door_slam'][0]
    solo = copy.deepcopy(ep)
    solo['shots'] = [dict(s) for s in solo['shots']]
    ki = c['shot']
    solo['shots'][ki] = dict(solo['shots'][ki],
                             sfx=[{kk: c[kk] for kk in ('name', 'line', 'anchor', 'offset', 'gain', 'pan', 'reverb')}])
    mm = bus(solo, lines, spans, dur)
    expect = np.asarray(S.make(c['name'], None, at=c['t']), np.float32)
    S.reseed(7)                                        # meme etat qu'au debut du bus
    i = int(c['t'] * SR)
    gotL = mm.L[i:i + len(expect)]
    wantL = expect * c['gain'] * min(1, 1 - c['pan'])
    ok('echantillon de depart exact (pas de decalage)',
       np.allclose(gotL, wantL, atol=1e-5), f"t={c['t']:.3f}s -> echantillon {i}")
    ok('rien avant le temps prevu', float(np.abs(mm.L[:i]).max()) == 0.)
    gotR = mm.R[i:i + len(expect)]
    want_ratio = min(1, 1 + c['pan']) / min(1, 1 - c['pan'])
    got_ratio = float(np.abs(gotR).max() / (np.abs(gotL).max() + 1e-12))
    ok('le pan demande est applique', abs(got_ratio - want_ratio) < 1e-3,
       f'rapport R/L mesure {got_ratio:.3f}, attendu {want_ratio:.3f}')


def test_pan():
    print('5. panoramique de la course : de la droite vers le centre')
    ep, lines, spans, dur = scene()
    p = SS.plan(ep, lines, spans, script=SCRIPT)
    runs = [c for c in p.cues if c['beat'] == 'threat_run']
    ok('la course produit plusieurs pas', len(runs) >= 5, f'{len(runs)} pas')
    pans = [c['pan'] for c in runs]
    ok('le pan part a droite et revient au centre',
       pans[0] > .4 and abs(pans[-1]) < .05 and all(x >= y - 1e-9 for x, y in zip(pans, pans[1:])),
       f'{pans[0]:+.2f} -> {pans[-1]:+.2f}')
    gains = [c['gain'] for c in runs]
    ok('la menace se rapproche : le niveau monte', gains[-1] > gains[0], f'{gains[0]:.2f} -> {gains[-1]:.2f}')
    mm = bus(p.apply(ep), lines, spans, dur)
    w = lambda x, t: float(np.sqrt((x[int((t - .02) * SR):int((t + .18) * SR)].astype(np.float64) ** 2).mean()))
    first, last = runs[0]['t'], runs[-1]['t']
    d0 = 20 * np.log10((w(mm.R, first) + 1e-12) / (w(mm.L, first) + 1e-12))
    d1 = 20 * np.log10((w(mm.R, last) + 1e-12) / (w(mm.L, last) + 1e-12))
    ok('premier pas nettement a droite dans le bus', d0 > 4.0, f'R-L {d0:+.2f} dB')
    ok('dernier pas centre', abs(d1) < 1.0, f'R-L {d1:+.2f} dB')


# ------------------------------------------------------------------ 6. priorite de la narration
def test_narration_priority():
    print('6. priorite de la narration (ducking)')
    ep, lines, spans, dur = scene()
    gaps = SS.narration_gaps(lines)
    ok('les trous de narration sont trouves', len(gaps) >= len(lines) - 1, f'{len(gaps)} trous')
    for a, b in gaps[:-1]:
        for l in lines:
            if l['start'] < b - 1e-6 and a < l['end'] - 1e-6:
                ok('un trou ne chevauche jamais une replique', False, f'trou ({a}, {b})'); return
    ok('aucun trou ne chevauche une replique', True)

    p = SS.plan(ep, lines, spans, script=SCRIPT)
    ing = [c for c in p.cues if c['in_gap']]
    out = [c for c in p.cues if not c['in_gap']]
    ok('des evenements sont poses dans les trous', bool(ing), f'{len(ing)}/{len(p.cues)}')
    if ing and out:
        ok('un evenement place dans un trou n est pas compense (niveau naturel)',
           max(c['gain'] for c in ing) <= 2.0, f"max {max(c['gain'] for c in ing):.2f}")
        ok('un evenement sous la voix est compense du ducking',
           min(c['gain'] for c in out) > 1.0, f"min {min(c['gain'] for c in out):.2f}")
    ok('le plan ne touche a aucun gain de voix / musique / fond',
       all(k not in p.apply(ep) for k in ('voice_gain', 'background_gain', 'music_gain')))

    # le masque de silence du mixeur coupe reellement le fond dans la fenetre demandee
    ep_b = p.apply(ep)
    m = MX.Mixer.__new__(MX.Mixer)
    m.ep = ep_b; m.lines = lines; m.duration = dur; m.N = int((dur + 1.) * SR)
    mute = m.silence_mask(spans)
    s = p.silences[0]; s0 = spans[s['shot']][0]
    mid = int((s0 + s['start'] + (s['end'] - s['start']) / 2) * SR)
    ok('le silence anormal coupe le fond', mute[mid] <= s['floor'] + 1e-6, f'masque = {mute[mid]:.3f}')
    ok('le fond est intact avant la fenetre de silence', mute[int((s0 - .5) * SR)] > .99)


# ------------------------------------------------------------------ 7. varietes d'espace
def test_spaces():
    print("7. variete des espaces (interieur / exterieur, pas la meme ambiance partout)")
    ep, lines, spans, dur = scene()
    p = SS.plan(ep, lines, spans, script=SCRIPT)
    names = [z['ambience'] for z in p.zones]
    ok('plusieurs espaces distincts', len(set(names)) >= 2, ' -> '.join(names))
    ok('2 a 4 lits d ambiance (preuve utile, pas un moteur)', 2 <= len(set(names)) <= 4, f'{len(set(names))}')
    ok('toutes les ambiances existent dans le moteur existant',
       all(z['ambience'] in __import__('hstudio.audio.ambience', fromlist=['x']).AMBIENCES for z in p.zones))
    ok('les zones couvrent les plans sans trou ni chevauchement',
       [z['shots'][0] for z in p.zones[1:]] == [z['shots'][1] + 1 for z in p.zones[:-1]],
       str([z['shots'] for z in p.zones]))
    revs = {c['reverb'] for c in p.cues}
    ok('la reverberation change selon l espace', len(revs) >= 2, str(sorted(revs)))
    tens = [t['value'] for t in p.tension]
    ok('la tension varie vraiment (pas rouge partout)',
       max(tens) - min(tens) > .5, f'{min(tens):.2f} .. {max(tens):.2f}')
    ok('un silence anormal fait retomber la tension', min(tens) < .3, f'min {min(tens):.2f}')


# ------------------------------------------------------------------ 8. pas de saturation
def test_headroom():
    print('8. niveaux : pas de saturation sur le bus des evenements')
    ep, lines, spans, dur = scene()
    p = SS.plan(ep, lines, spans, script=SCRIPT)
    mm = bus(p.apply(ep), lines, spans, dur)
    # le mixeur applique encore .34 et le ducking (<=1) aux bruitages avant la somme finale
    for ch, x in (('L', mm.L), ('R', mm.R)):
        peak = float(np.abs(x).max()) * .34
        ok(f'bus {ch} sous le plein echelle apres le coefficient du mixeur', peak < 1.0, f'pic {peak:.3f}')
    ok('aucun NaN / infini', bool(np.isfinite(mm.L).all() and np.isfinite(mm.R).all()))
    ok('le bus contient bien du son', float(np.abs(mm.L).max()) > 0)


if __name__ == '__main__':
    test_detect(); test_determinism(); test_integrity(); test_sync()
    test_pan(); test_narration_priority(); test_spaces(); test_headroom()
    print()
    if FAILS:
        print(f'{len(FAILS)} test(s) en echec :')
        for f in FAILS: print('  -', f)
        sys.exit(1)
    print('tous les tests passent.')
