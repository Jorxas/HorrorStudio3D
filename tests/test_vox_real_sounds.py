"""python tests/test_vox_real_sounds.py   (hors ligne, sans GPU)

Les vrais sons du moteur VOXEL (library/audio_real, hstudio/voxelgpu/audio.py) :
  * la bibliothèque se charge sans refus, chaque variante a un crédit complet, aucun fichier n'est silencieux, écrêté ou tronqué ;
  * PAR DÉFAUT le mix est identique au bit près à la synthèse d'avant (les films existants ne changent pas), `samples: false` aussi ;
  * `samples: true` change le mix, il est reproductible (même graine = mêmes bits), et le fournisseur est restauré après le mix ;
  * chaque banque a son CREDITS.json et sa licence recopiée."""
import json, sys, tempfile, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio import audio as _A                                  # noqa: installe le fournisseur historique
from hstudio.audio import library as L, synth as S
from hstudio.voxelgpu import audio as VA

REAL = ROOT / 'library' / 'audio_real'
BAD = []


def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ECHEC'), name, ('— ' + str(detail)) if detail else '');
    if not ok: BAD.append(name)


def contract(audio):
    steps = [[1.0 + .5 * k, 0., 0., 0., 1 if k % 2 else -1] for k in range(6)]
    return dict(duration=7.0, audio=audio, stages=[dict(world='pluie', t0=0., t1=7., foley_steps={'a': steps})])


def mix(audio):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'm.wav'; VA.compose(contract(audio), str(p))
        with wave.open(str(p), 'rb') as w: return np.frombuffer(w.readframes(w.getnframes()), '<i2').copy()


def main():
    lib = L.SoundLibrary(root=str(REAL)).load()
    check('bibliothèque réelle : chargée', len(lib.events) >= 100, f'{len(lib.events)} événements')
    check('bibliothèque réelle : aucun refus de licence ou de fichier', not lib.problems, lib.problems[:2])
    man = json.loads((REAL / 'manifest.json').read_text(encoding='utf-8'))
    n = bad = 0; clip = silent = trunc = 0; banks = set()
    for ev, e in man['events'].items():
        for v in e['variants']:
            n += 1; c = v.get('credit') or {}; banks.add(c.get('bank'))
            if not all(c.get(k) for k in L.CREDIT_FIELDS) or c.get('redistribute') is not True: bad += 1
            a = L.read_wav(str(REAL / v['file']))[0]
            if float(np.max(np.abs(a))) < .05: silent += 1
            if float(np.mean(np.abs(a) >= .999)) > .001: clip += 1
            if len(a) < int(.03 * 44100) or abs(float(a[0])) > .2: trunc += 1
    check(f'{n} variantes : crédit complet et redistribution vraie', bad == 0, f'{bad} incomplètes')
    check('aucun fichier silencieux, écrêté ou tronqué', clip == silent == trunc == 0, f'écrêtés {clip}, silencieux {silent}, tronqués/abrupts {trunc}')
    check('chaque banque a son CREDITS.json', all((REAL / 'banks' / b / 'CREDITS.json').exists() for b in banks if b), sorted(x for x in banks if x))
    check('licences recopiées (oculus, wyzowl)', all((REAL / 'banks' / b / 'LICENSE.txt').exists() for b in ('oculus', 'wyzowl')))
    nocred = [b for b in banks if b and json.loads((REAL / 'banks' / b / 'CREDITS.json').read_text(encoding='utf-8')).get('credit_required') and not json.loads((REAL / 'banks' / b / 'CREDITS.json').read_text(encoding='utf-8')).get('credit_text')]
    check('toute banque à crédit exigé porte son texte de crédit', not nocred, nocred)

    base = dict(sfx=[dict(t=1.0, name='door_slam', gain=.8), dict(t=3.0, name='creak', gain=.8), dict(t=4.5, name='footsteps_walk', gain=.6, dur=1.5)], ambience=[dict(t0=0., t1=7., name='rain', gain=.3)], foley=dict(steps=True, gain=.5))
    prev = S.SAMPLE_PROVIDER
    a0 = mix(dict(base)); a1 = mix(dict(base, samples=False)); b0 = mix(dict(base, samples=True)); b1 = mix(dict(base, samples=True))
    check('défaut = synthèse d\'avant (bits identiques à samples:false)', np.array_equal(a0, a1))
    check('samples:true change le mix', not np.array_equal(a0, b0), f'écart moyen {float(np.mean(np.abs(a0.astype(float) - b0))):.0f} / 32767')
    check('samples:true reproductible (mêmes bits)', np.array_equal(b0, b1))
    check('fournisseur d\'échantillons restauré après le mix', S.SAMPLE_PROVIDER is prev)
    check('mix valide (fini, borné)', all(np.max(np.abs(x.astype(float))) <= 32767 for x in (a0, b0)) and np.max(np.abs(b0)) > 1000, f'pics {int(np.max(np.abs(a0)))} / {int(np.max(np.abs(b0)))}')
    rms = lambda x: float(np.sqrt(np.mean((x.astype(float) / 32768) ** 2)))
    print(f'     niveaux (rms) : synthèse {20 * np.log10(rms(a0)):.1f} dBFS, réel {20 * np.log10(rms(b0)):.1f} dBFS')
    print('\n' + (f'{len(BAD)} échec(s) : {BAD}' if BAD else 'Tout est OK.')); sys.exit(1 if BAD else 0)


if __name__ == '__main__': main()
