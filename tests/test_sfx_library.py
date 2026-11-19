"""Offline tests for the sound library (no network, no ffmpeg, no API, no cost).

    python tests/test_sfx_library.py

Checks the contract of hstudio/audio/library.py: licences, determinism, relative normalisation,
timing, duration fitting, fallback when an asset is missing, and the real mixer cue path.
"""
import os, sys, json, shutil, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hstudio.audio                                  # installs the provider on synth
from hstudio.audio import synth as S, library as L, mixer as MX

SR = S.SR
LIB = L.LIB
FAILS = []


def ok(name, cond, info=''):
    print(('  OK   ' if cond else '  FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: FAILS.append(name)


def db(a, b): return 20 * np.log10((a + 1e-12) / (b + 1e-12))


# ------------------------------------------------------------------ 1. manifest and licences
def test_manifest():
    print('1. manifeste et licences')
    rep = LIB.check()
    ok('manifeste chargé', bool(rep['events']), f"{len(rep['events'])} événements")
    ok('aucun problème (licence / fichier / lecture)', not rep['problems'], json.dumps(rep['problems'], ensure_ascii=False)[:300])
    for key, ev in rep['events'].items():
        for v in ev['variants']:
            if not v.get('ok'): FAILS.append(f'asset illisible {v["file"]}'); print(f"  FAIL asset illisible {v['file']}")
    ok('toutes les variantes sont lisibles et non vides',
       all(v.get('ok') and v.get('seconds', 0) > .01 for ev in rep['events'].values() for v in ev['variants']))
    ok('chaque clé couverte existe aussi en synthèse (fallback possible)',
       all(k in S.SFX for k in rep['covered']), f"{len(rep['covered'])} clés couvertes")
    return rep


# ------------------------------------------------------------------ 2. determinism
def test_determinism(rep):
    print('2. déterminisme')
    key = rep['covered'][0]
    LIB.seed = 42; LIB.enabled = True
    a = LIB.render(key, None, 3.25); b = LIB.render(key, None, 3.25)
    ok('même (clé, temps, graine) -> échantillon identique', a is not None and np.array_equal(a, b))
    LIB.seed = 43; c = LIB.render(key, None, 3.25)
    LIB.seed = 42
    ok('graine différente -> rendu différent', c is not None and not np.array_equal(a, c))
    multi = [k for k in rep['covered'] if len(rep['events'][k]['variants']) > 1]
    ok('des événements ont plusieurs variantes', bool(multi), f'{len(multi)} événements')
    if multi:
        k = multi[0]
        sigs = {LIB.render(k, None, t / 10.).tobytes() for t in range(40)}
        ok(f'variations sur 40 cues de « {k} »', len(sigs) > 3, f'{len(sigs)} rendus distincts')
    S.reseed(99); base = S.synthesize('shatter' if 'shatter' in S.SFX else 'glass_shatter')
    S.reseed(99); LIB.render(key, None, 3.25); after = S.synthesize('shatter' if 'shatter' in S.SFX else 'glass_shatter')
    ok('un rendu de la bibliothèque ne consomme pas le flux aléatoire de la synthèse', np.array_equal(base, after))


# ------------------------------------------------------------------ 3. levels (the validated mix balance)
def test_levels(rep):
    """the property that protects the mix validated by the owner: a sample is never LOUDER than the
    procedural sound it replaces. Being quieter is safe (and unavoidable on very peaky real material:
    a sample normalised at -3 dBFS cannot be made louder without clipping)."""
    print('3. normalisation relative (équilibre du mix validé)')
    louder = []; quiet = []
    for key, ev in rep['events'].items():
        a, b = ev['synth_short'], ev['served_short']
        if not a or not b: continue
        d = db(b, a)
        if d > 3.0: louder.append((key, round(d, 1)))
        elif d < -6.0: quiet.append((key, round(d, 1), [v['kind'] for v in ev['variants']][0]))
    ok('aucun événement ne sonne PLUS FORT que la synthèse qu\'il remplace (+3 dB max)', not louder, str(louder))
    placeholders_off = [q for q in quiet if q[2] != 'recording']
    ok('les substituts synthétiques restent dans ±6 dB', not placeholders_off, str(placeholders_off))
    if quiet: print(f"     (à signaler : {quiet} — enregistrements très transitoires, source à améliorer)")
    peaks = [float(np.abs(LIB.render(k, None, 1.0)).max()) for k in rep['covered']]
    ceil = float(LIB.defaults['peak_ceiling'])
    ok(f'aucun dépassement de {ceil} (marge avant le mixeur)', max(peaks) <= ceil + 1e-4, f'pic max {max(peaks):.3f}')


# ------------------------------------------------------------------ 4. timing
def test_timing(rep):
    print('4. timing')
    dead, late = [], []
    for key in rep['covered']:
        a = LIB.render(key, None, 2.0); env = np.abs(a); p = float(env.max())
        start = int(np.argmax(env > .02 * p)) / SR                  # no dead air at the head
        hit = int(np.argmax(env > .25 * p)) / SR                    # the main hit
        if start > .006: dead.append((key, round(start * 1000, 1)))
        if LIB.events[key].get('align') == 'transient' and hit > .03: late.append((key, round(hit * 1000, 1)))
    ok('aucun silence en tête : le son démarre sur le temps de la cue (<6 ms)', not dead, str(dead))
    ok('événements d\'impact : le coup principal tombe sur la cue (<30 ms)', not late, str(late))


# ------------------------------------------------------------------ 5. duration
def test_duration(rep):
    print('5. durée demandée')
    key = rep['covered'][0]
    long = max(rep['covered'], key=lambda k: max(v['seconds'] for v in rep['events'][k]['variants']))
    a = LIB.render(long, .25, 1.0)
    ok(f'« {long} » tronqué à la durée demandée', a is not None and abs(len(a) / SR - .25) < .01, f'{len(a) / SR:.3f} s')
    tiled = L.tile(LIB.render(key, None, 1.0), int(1.5 * SR))
    ok('bouclage exact (événements loop)', len(tiled) == int(1.5 * SR))


# ------------------------------------------------------------------ 6. missing asset / switch off
def test_fallback(rep):
    print('6. comportement si asset absent ou bibliothèque coupée')
    ok('clé inconnue de la bibliothèque -> None', LIB.render('sting', None, 1.0) is None)
    ok('synthèse toujours disponible pour cette clé', float(np.abs(S.make('sting', at=1.0)).max()) > 0)
    tmp = tempfile.mkdtemp(); lib2 = L.SoundLibrary(tmp)
    os.makedirs(os.path.join(tmp, 'sfx'), exist_ok=True)
    man = {'version': 1, 'events': {
        'creak': {'variants': [{'file': 'sfx/nope.wav', 'credit': dict(source='x', url='x', author='x', licence='CC0-1.0', verified='x', redistribute=True)}]},
        'boom': {'variants': [{'file': 'sfx/nope2.wav', 'credit': dict(source='x', url='x', author='x', licence='Commercial', verified='x', redistribute=False)}]},
        'knock': {'variants': [{'file': 'sfx/nope3.wav', 'credit': dict(source='x', url='x', licence='CC0-1.0', verified='x', redistribute=True)}]}}}
    with open(os.path.join(tmp, 'manifest.json'), 'w', encoding='utf-8') as f: json.dump(man, f)
    lib2.load()
    whys = {p['event']: p['why'] for p in lib2.problems}
    ok('fichier absent -> refusé et signalé', 'absent' in whys.get('creak', ''), whys.get('creak', ''))
    ok('licence non redistribuable -> refusée', 'redistribution' in whys.get('boom', ''), whys.get('boom', ''))
    ok('crédit incomplet -> refusé', 'champs manquants' in whys.get('knock', ''), whys.get('knock', ''))
    ok('aucun événement chargé, tout retombe en synthèse', lib2.render('creak', None, 1.) is None and not lib2.events)
    shutil.rmtree(tmp, ignore_errors=True)
    LIB.enabled = False
    ok('interrupteur épisode / env -> plus aucun sample', LIB.render(rep['covered'][0], None, 1.) is None)
    LIB.enabled = True


# ------------------------------------------------------------------ 7. the real mixer path
def mix_cues(enabled, seed=7):
    """hstudio/audio/mixer.py sfx_cues() on a 2-shot episode, without ffmpeg / voice"""
    dur = 8.0
    ep = {'seed': seed, 'shots': [
        {'lines': [0, 0], 'sfx': [{'name': 'knock', 'at': .5, 'repeat': 3, 'gap': .45}, {'name': 'creak', 'at': 2.2}]},
        {'lines': [1, 1], 'sfx': [{'name': 'door_slam', 'line': 1, 'anchor': 'end', 'offset': .2}]}]}
    lines = [{'start': .2, 'end': 1.8, 'sfx': [{'name': 'drip', 'offset': .3}]}, {'start': 4.2, 'end': 5.6}]
    m = MX.Mixer.__new__(MX.Mixer)
    m.lines = lines; m.ep = ep; m.duration = dur; m.style = 'pixel3d'; m.wd = tempfile.mkdtemp()
    m.N = int((dur + 1.) * SR)
    m.voice = np.zeros(m.N, np.float32); m.L = np.zeros(m.N, np.float32); m.R = np.zeros(m.N, np.float32); m.REV = np.zeros(m.N, np.float32)
    S.reseed(seed)
    if enabled is not None: ep['sfx_library'] = enabled       # None: no key at all, the default decides
    from hstudio.audio.library import env_default
    m.lib = LIB; LIB.seed = seed; LIB.used = {}
    LIB.enabled = bool(ep.get('sfx_library', env_default()))  # the same line as Mixer.__init__
    m.foley = [{'name': 'step_wood', 't': 3.0 + .42 * i, 'gain': .3} for i in range(6)]
    m.sfx_cues([(0., 4.), (4., 8.)])
    shutil.rmtree(m.wd, ignore_errors=True)
    return m.L + m.R, dict(LIB.used)


def test_default():
    """the library is opt-in: an episode written before it existed must not change sound on its own"""
    print("8. par défaut : un épisode sans la clé garde sa synthèse")
    import os
    from hstudio.audio.library import env_default
    keep = os.environ.pop('HSTUDIO_SFX_LIBRARY', None)
    try:
        ok('sans variable d\'environnement, le défaut est « éteint »', env_default() is False)
        a, ua = mix_cues(None)           # no key at all: whatever the default decides
        b, ub = mix_cues(False)          # explicitly off
        c, _ = mix_cues(True)            # explicitly on
        ok('sans la clé : aucun sample servi', not ua, json.dumps(ua))
        ok('sans la clé = « sfx_library »: false, au bit près', np.array_equal(a, b))
        ok('sans la clé != opt-in explicite (la bibliothèque s\'entend)', not np.array_equal(a, c))
        os.environ['HSTUDIO_SFX_LIBRARY'] = '1'
        ok('HSTUDIO_SFX_LIBRARY=1 : opt-in global pour une écoute', env_default() is True)
        d, ud = mix_cues(None)
        ok('  et alors la bibliothèque sert comme en opt-in explicite', np.array_equal(d, c) and bool(ud))
    finally:
        os.environ.pop('HSTUDIO_SFX_LIBRARY', None)
        if keep is not None: os.environ['HSTUDIO_SFX_LIBRARY'] = keep
    LIB.enabled = True


def test_mixer():
    print('7. chemin réel du mixeur (sfx_cues)')
    a, used = mix_cues(True); b, _ = mix_cues(True); c, _ = mix_cues(False)
    ok('le mixeur produit du son avec la bibliothèque', float(np.abs(a).max()) > 0)
    ok('deux rendus identiques (mix déterministe)', np.array_equal(a, b))
    ok('"sfx_library": false redonne exactement la synthèse', float(np.abs(c).max()) > 0 and not np.array_equal(a, c))
    ok('des samples ont bien été servis par le mixeur', sum(used.values()) >= 10, json.dumps(used))
    # the mix must never get LOUDER: real bruitages are peakier than the dense synthesis, so on a
    # cue-heavy excerpt they legitimately come out quieter (reported, not failed - see docs/AUDIO_LIBRARY.md)
    d = db(L.rms(a), L.rms(c))
    ok('le mix ne devient jamais plus fort qu\'en synthèse (+2 dB max)', d <= 2.0, f'{d:+.2f} dB')
    if d < -3: print(f'     (à signaler : {d:+.2f} dB sur cet extrait très dense en cues)')
    LIB.enabled = True


if __name__ == '__main__':
    rep = test_manifest()
    if not rep['events']:
        print('\nAucun événement : lance d\'abord `python tools/sfxlib.py bake`'); sys.exit(1)
    test_determinism(rep); test_levels(rep); test_timing(rep); test_duration(rep); test_fallback(rep); test_mixer(); test_default()
    print(f"\n{'ÉCHECS : ' + ', '.join(FAILS) if FAILS else 'TOUT OK'}")
    sys.exit(1 if FAILS else 0)
