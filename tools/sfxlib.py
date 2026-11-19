"""Sound library tool (no network, no API, no cost).

    python tools/sfxlib.py bake      # (re)build library/audio: variant files + manifest.json + LICENSES.md
    python tools/sfxlib.py check     # validate the manifest offline: licences, files, levels, coverage
    python tools/sfxlib.py ab        # A/B proof: the same cue list rendered synthetic vs library

`bake` writes the *fallback* library the mission asks for when no third-party sample can be redistributed:
each file is produced here, from this repository's own synthesis, then treated like a recorded bruitage
(DC removal, high-end tilt, small room, soft saturation, trimmed to the transient, peak at -3 dBFS).
They are honest placeholders with a CC0 credit block pointing at this tool - not recordings - and they exist
so the loader, the variations, the relative normalisation and the timing can be tested and heard offline.
To install real recordings, drop them in `library/audio/sfx/<event>/` and give each one a verified credit
block in the manifest (see docs/AUDIO_LIBRARY.md); nothing else changes.
"""
import json, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hstudio.audio                              # registers ambience + the library provider
from hstudio.audio import synth as S, library as L

SR = S.SR
ROOT = L.ROOT
# event key -> (variants, pitch jitter in cents, gain jitter in dB, amount of room)
BAKE = {
    'step': (4, 120, 2.5, .22), 'step_wood': (4, 120, 2.5, .22), 'step_hard': (4, 110, 2.5, .26), 'step_grass': (4, 130, 2.5, .16),
    'cloth': (3, 100, 2.0, .15), 'pickup': (3, 100, 2.0, .18), 'paper': (3, 110, 2.0, .15), 'drip': (3, 150, 2.5, .30),
    'door_handle': (3, 60, 1.5, .18), 'creak': (3, 80, 1.5, .25), 'door_slam': (3, 40, 1.0, .35), 'knock': (2, 40, 1.0, .30),
    'metal_hit': (3, 70, 1.5, .40), 'glass_crack': (3, 60, 1.5, .25), 'boom': (2, 30, 0.8, .30),
}
CREDIT = {
    'kind': 'synthetic_placeholder',      # <- NOT a recording: synthesis of this repo, reworked. See docs/AUDIO_LIBRARY.md
    'source': 'Horror Studio - tools/sfxlib.py bake (synthèse locale retravaillée, aucun enregistrement tiers)',
    'url': 'local:tools/sfxlib.py',
    'author': 'Horror Studio (procédural)',
    'licence': 'CC0-1.0',
    'redistribute': True,
}


def fconv(x, ir):
    n = len(x) + len(ir) - 1; nf = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:n].astype(np.float32)


def room_ir(seed, dur=.22, fc=6000):
    r = np.random.default_rng(seed); n = int(dur * SR); t = np.arange(n) / SR
    ir = r.standard_normal(n).astype(np.float32) * np.exp(-t * 14.)
    ir = S.lp(ir, fc); ir[:int(.004 * SR)] = 0
    return ir / (np.abs(ir).sum() + 1e-9)


def shape(x, seed, room=.2, tilt=.35, peak_db=-3.):
    """make a procedural sound behave like a recorded one: no DC, softer top, a bit of space, trimmed"""
    x = np.asarray(x, np.float32)
    x = x - float(x.mean())
    x = (x - tilt * S.hp(x, 6500)).astype(np.float32)
    wet = fconv(x, room_ir(seed))
    wet *= L.rms(x) / (L.rms(wet) + 1e-9)
    y = np.pad(x, (0, len(wet) - len(x))) + room * wet
    y = np.tanh(y * 1.3) / 1.3
    y = L.align_attack(y, pre=.003)
    env = np.convolve(np.abs(y), np.ones(441, np.float32) / 441, 'same')
    p = float(env.max()) if len(env) else 0.
    live = np.nonzero(env > max(1e-5, p * .0015))[0]
    if len(live): y = y[:min(len(y), int(live[-1]) + int(.03 * SR))]
    y = L.edges(y, .0004, .012)
    pk = float(np.abs(y).max()) if len(y) else 0.
    if pk > 1e-9: y = y * (10 ** (peak_db / 20.) / pk)
    return y.astype(np.float32)


# ------------------------------------------------------------------ bake
def existing_recordings():
    """real recordings already imported (tools/sfx_import.py) - bake must never erase them"""
    path = os.path.join(ROOT, 'manifest.json')
    if not os.path.exists(path): return {}
    man = json.load(open(path, encoding='utf-8'))
    out = {}
    for key, ev in (man.get('events') or {}).items():
        real = [v for v in (ev.get('variants') or []) if (v.get('credit') or {}).get('kind') == 'recording']
        if real: out[key] = dict(ev, variants=real, align='transient' if key in L.IMPULSIVE_EVENTS else 'attack')
    return out


def bake():
    stamp = time.strftime('%Y-%m-%d')
    real = existing_recordings()
    events = dict(real); rows = []
    for key, (nv, pj, gj, room) in BAKE.items():
        if key in real:                   # a real recording wins: no synthetic placeholder for this event
            print(f'  = {key} : {len(real[key]["variants"])} enregistrement(s) réel(s) conservé(s), pas de substitut')
            continue
        variants = []
        for i in range(nv):
            S.reseed(1000 + 97 * i + 7 * len(key))
            raw = S.synthesize(key)
            a = shape(raw, seed=4000 + 31 * i + len(key), room=room)
            rel = f'sfx/{key}/{key}_{i + 1:02d}.wav'
            L.write_wav(os.path.join(ROOT, rel), a)
            credit = dict(CREDIT, verified=f'{stamp} : fichier produit par ce dépôt (tools/sfxlib.py bake), aucune source externe')
            variants.append(dict(file=rel, weight=1.0, gain_db=0.0, credit=credit))
            rows.append((key, rel, len(a) / SR, credit))
        events[key] = dict(description=S.SFX_DESCRIPTIONS.get(key, ''), loop=False,
                           align='transient' if key in L.IMPULSIVE_EVENTS else 'attack',
                           pitch_jitter=pj, gain_jitter_db=gj, variants=variants)
    manifest = {
        'version': 1,
        'generated': stamp,
        'notes': ("Bibliothèque de bruitages. Une clé d'événement (les mêmes que hstudio/audio/synth.py SFX) -> "
                  "une ou plusieurs variantes. Les fichiers livrés ici sont des SUBSTITUTS générés localement "
                  "(tools/sfxlib.py bake) : aucun enregistrement tiers n'est redistribué. Pour installer de vrais "
                  "bruitages, voir docs/AUDIO_LIBRARY.md ; chaque variante doit porter un bloc credit complet "
                  "(source, url, author, licence, verified) et redistribute=true, sinon le chargeur la refuse."),
        'defaults': {'match': 'synth_short', 'align': 'attack', 'gain_db': 0.0, 'target_rms': 0.06},
        'events': events,
    }
    with open(os.path.join(ROOT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    n_real = sum(len(ev['variants']) for ev in real.values())
    lic = ['# Licences des bruitages (library/audio)', '',
           'Une ligne par fichier redistribué. Le chargeur (`hstudio/audio/library.py`) refuse toute variante',
           'dont ce bloc est incomplet ou dont `redistribute` n\'est pas `true`.', '',
           f'- **{n_real} enregistrements réels** (`kind: recording`) : de vrais bruitages, licence vérifiée fichier par fichier.',
           f'- **{len(rows)} substituts synthétiques** (`kind: synthetic_placeholder`) : **ce ne sont PAS des enregistrements**,',
           '  c\'est la synthèse de ce dépôt retravaillée, en attendant de vrais sons pour ces événements.', '',
           '## Enregistrements réels', '',
           '| fichier | licence | auteur | source | vérifié |', '|---|---|---|---|---|']
    for key, ev in sorted(real.items()):
        for v in ev['variants']:
            c = v['credit']
            lic.append(f"| `{v['file']}` | {c['licence']} | {c.get('author')} | [{c.get('source')}]({c.get('url')}) | {c.get('verified')} |")
    if not n_real: lic.append('| _(aucun pour l\'instant)_ | | | | |')
    lic += ['', '## Substituts synthétiques (pas des enregistrements)', '',
            '| fichier | durée | licence | auteur | source | vérifié |', '|---|---|---|---|---|---|']
    for key, rel, dur, c in rows:
        lic.append(f"| `{rel}` | {dur:.2f} s | {c['licence']} | {c['author']} | {c['source']} | {c['verified']} |")
    lic += ['', '## Ce qui n\'est PAS ici', '',
            'Aucun pack tiers (Freesound, BBC Sound Effects, Soundsnap, ZapSplat...) n\'a été téléchargé ni',
            'redistribué : leurs licences doivent être vérifiées fichier par fichier par un humain avant ajout',
            '(BBC Sound Effects et ZapSplat, par exemple, interdisent la redistribution du fichier source).', '']
    with open(os.path.join(ROOT, 'LICENSES.md'), 'w', encoding='utf-8') as f: f.write('\n'.join(lic))
    print(f'{len(rows)} fichiers, {len(events)} événements -> {ROOT}')
    return manifest


# ------------------------------------------------------------------ check
def check(as_json=False):
    rep = L.LIB.check()
    if as_json: print(json.dumps(rep, ensure_ascii=False, indent=2)); return rep
    print(f"manifeste : {os.path.join(rep['root'], 'manifest.json')}  (version {rep['version']})")
    print(f"{'événement':16} {'var':>3} {'type':>10} {'durées (s)':>22} "
          f"{'écart court':>12} {'écart rms':>10}   (court = 50 ms les plus forts, la cible visée)")
    n_real = n_fake = 0
    for key, ev in rep['events'].items():
        durs = ' '.join(f"{v.get('seconds', 0):.2f}" for v in ev['variants'])
        kinds = {v.get('kind') for v in ev['variants']}
        real = len([v for v in ev['variants'] if v.get('kind') == 'recording'])
        n_real += real; n_fake += len(ev['variants']) - real
        tag = 'RÉEL' if kinds == {'recording'} else ('mixte' if 'recording' in kinds else 'substitut')
        def ecart(a, b): return f"{20 * np.log10((b + 1e-12) / (a + 1e-12)):+.1f} dB" if (a and b) else '-'
        print(f"{key:16} {len(ev['variants']):>3} {tag:>10} {durs:>22} "
              f"{ecart(ev['synth_short'], ev['served_short']):>12} {ecart(ev['synth_rms'], ev['served_rms']):>10}")
    print(f"\nfichiers : {n_real} enregistrements RÉELS + {n_fake} substituts synthétiques (PAS des enregistrements)")
    print(f"couverts par des samples : {len(rep['covered'])}  |  encore 100% synthétiques : {len(rep['still_synthetic'])}")
    if rep['library_only']: print(f"clés présentes seulement dans la bibliothèque : {', '.join(rep['library_only'])}")
    if rep['problems']:
        print('\nPROBLÈMES :')
        for p in rep['problems']: print(f"  - {p['event']} / {p['file']} : {p['why']}")
    else:
        print('aucun problème (licences complètes, fichiers lisibles)')
    return rep


# ------------------------------------------------------------------ A/B
CUES = [('step_wood', .30), ('step_wood', .30), ('step_wood', .30), ('step_wood', .30),
        ('door_handle', .55), ('creak', .65), ('door_slam', .40), ('knock', .70),
        ('cloth', .55), ('pickup', .50), ('paper', .45), ('drip', .40),
        ('metal_hit', .45), ('glass_crack', .55), ('boom', .50)]
GAP = 1.1


def timeline(use_library, seed=7):
    L.LIB.seed = seed; L.LIB.enabled = use_library
    S.reseed(seed)
    n = int((len(CUES) * GAP + 3.) * SR); out = np.zeros(n, np.float32); marks = []
    for i, (name, gain) in enumerate(CUES):
        t = .4 + i * GAP
        a = S.make(name, at=t) * gain
        j = int(t * SR); m = min(len(a), n - j); out[j:j + m] += a[:m]
        marks.append((name, t, L.rms(a[:m])))
    return out, marks


def ab(out_dir=os.path.join('docs', 'audio_ab')):
    os.makedirs(out_dir, exist_ok=True)
    syn, ms = timeline(False); lib, ml = timeline(True)
    L.LIB.enabled = True
    gap = np.zeros(int(1.2 * SR), np.float32)
    L.write_wav(os.path.join(out_dir, 'ab_synth.wav'), syn)
    L.write_wav(os.path.join(out_dir, 'ab_library.wav'), lib)
    L.write_wav(os.path.join(out_dir, 'ab_montage.wav'), np.concatenate([syn, gap, lib]))
    rows = []
    print(f"{'événement':14} {'rms synth':>10} {'rms biblio':>11}  écart   source")
    for (n1, t, r1), (n2, _, r2) in zip(ms, ml):
        d = 20 * np.log10((r2 + 1e-12) / (r1 + 1e-12))
        src = 'bibliothèque' if L.LIB.has(n1) else 'synthèse (pas de sample)'
        rows.append(dict(event=n1, t=round(t, 2), rms_synth=round(r1, 5), rms_library=round(r2, 5), delta_db=round(d, 2), source=src))
        print(f'{n1:14} {r1:>10.5f} {r2:>11.5f} {d:>+7.1f} dB  {src}')
    with open(os.path.join(out_dir, 'ab.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(cues=rows, used=L.LIB.used, note='même liste de cues, même gains : seule la source du son change'),
                  f, ensure_ascii=False, indent=2)
    try: waveform_png(syn, lib, ms, os.path.join(out_dir, 'ab_waveforms.png'))
    except Exception as e: print(f'(PNG non généré : {e})')
    print(f'\n-> {out_dir}/ab_montage.wav (synthèse, 1.2 s de silence, bibliothèque)')
    return rows


def waveform_png(syn, lib, marks, path, w=1280, h=420):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (w, h), (18, 18, 22)); d = ImageDraw.Draw(img)
    n = max(len(syn), len(lib))
    for row, (sig, label) in enumerate(((syn, 'A - synthese actuelle'), (lib, 'B - bibliotheque de bruitages'))):
        y0 = 60 + row * 180; amp = 70
        d.text((14, y0 - 48), label, fill=(230, 230, 235))
        d.line((0, y0, w, y0), fill=(60, 60, 70))
        step = max(1, n // w)
        for x in range(w):
            seg = sig[x * step:(x + 1) * step]
            if not len(seg): continue
            v = float(np.abs(seg).max()) * amp
            d.line((x, y0 - v, x, y0 + v), fill=(150, 210, 255) if row else (255, 170, 120))
    for name, t, _ in marks:
        x = int(t * SR / n * w)
        d.line((x, 20, x, 36), fill=(120, 120, 130))
        d.text((x + 2, 16), name[:10], fill=(150, 150, 160))
    d.text((14, h - 22), 'memes cues, memes gains : seule la source du son change (tools/sfxlib.py ab)', fill=(170, 170, 180))
    img.save(path)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'bake': bake(); check()
    elif cmd == 'ab': ab(*sys.argv[2:3])
    else:
        rep = check('--json' in sys.argv)
        sys.exit(1 if rep['problems'] else 0)
