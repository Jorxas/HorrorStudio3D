"""Import real CC0 / public-domain bruitages from Wikimedia Commons into library/audio.

    python tools/sfx_import.py survey              # search + READ THE LICENCE OF EACH FILE, download nothing
    python tools/sfx_import.py fetch --dry         # the curated plan, licences re-checked, still no download
    python tools/sfx_import.py fetch               # download ONLY what was accepted, convert, update the manifest

Rules enforced here, in this order:
1. the licence of every candidate is read from the Commons API (`extmetadata`) BEFORE any download;
2. only an allow-list of licences that permit redistribution is accepted (CC0 / public domain);
   anything else - including CC-BY and CC-BY-SA - is refused and logged, never downloaded;
3. every accepted file keeps its proof in `library/audio/IMPORT_LOG.json` (title, page URL, author,
   licence, verdict, sha256 of the source and of the file actually written);
4. the file is converted once to the studio format (mono 44100 Hz 16 bit WAV) so hstudio needs no new
   dependency at mix time; `soundfile` is an IMPORT-time dependency only, never imported by the mixer.

No API key, no paid service, no scraping: the public MediaWiki API with a proper User-Agent.
"""
import hashlib, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hstudio.audio                                     # noqa: registers the provider
from hstudio.audio import synth as S, library as L

API = 'https://commons.wikimedia.org/w/api.php'
PACE = 6.0          # seconds between two Commons requests (politeness + HTTP 429)
UA = 'HorrorStudio-SFX/0.3 (local sound library for a personal film project; batch of a few files)'
# licences that allow redistribution inside the code / the ZIP
OK_LICENCES = ('cc0', 'cc-zero', 'public domain', 'publicdomain', 'pd-self', 'pd-us', 'no restrictions')
BAD_HINTS = ('by-sa', 'by-nc', 'by-nd', 'cc by', 'cc-by', 'gfdl', 'fair use', 'non-commercial')
# search term -> event key of synth.SFX (priority categories for the story engine)
QUERIES = {
    'step_hard': ['footstep concrete', 'footsteps hard floor'],
    'step_wood': ['footstep wood', 'footsteps wooden floor'],
    'step_grass': ['footstep gravel', 'footsteps grass'],
    'creak': ['door creak', 'creaking door'],
    'door_slam': ['door slam', 'door closing'],
    'knock': ['knock door', 'door knocking'],
    'drip': ['water drip', 'dripping water'],
    'glass_crack': ['glass break', 'breaking glass'],
    'paper': ['paper rustle', 'turning page'],
    'metal_hit': ['metal impact', 'metal clang'],
    'thunder': ['thunder'],
    'heartbeat': ['heartbeat'],
}
# Hand-picked from SURVEY.json: REAL recordings only (no speech, no music, no "pronunciation" file).
PLAN = [
    dict(event='creak',       title='File:Door handle creaking.ogg',                               max_len=2.5),
    dict(event='creak',       title='File:LL-Q1860 (eng)-Knites-Sound recording. Door creaks.wav', max_len=2.5),
    dict(event='creak',       title='File:Rusty metal door clasp.ogg',                             max_len=2.5),
    dict(event='door_slam',   title='File:Closing an old door.ogg',                                max_len=2.0),
    dict(event='door_slam',   title='File:Garage door closing.ogg',                                max_len=2.0),
    dict(event='door_slam',   title='File:Elevator door closing.ogg',                              max_len=2.0),
    dict(event='knock',       title='File:Knocking on wood or door.ogg',                           max_len=2.2),
    dict(event='knock',       title='File:Door knocker audio.ogg',                                 max_len=2.2),
    dict(event='knock',       title='File:Knock on door.wav',                                      max_len=2.2),
    dict(event='door_handle', title='File:Rusty metal door clasp 02.ogg',                          max_len=1.2),
    dict(event='metal_hit',   title='File:Metal cabinet door jarring.ogg',                         max_len=1.6),
    dict(event='drip',        title='File:LL-Q1860 (eng)-Knites-Water dripping.wav',               max_len=1.0),
    dict(event='paper',       title='File:Turning a page.ogg',                                     max_len=1.2),
]


def api(**params):
    params.setdefault('format', 'json'); params.setdefault('formatversion', '2')
    req = urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def strip_html(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', str(s or ''))).strip()


def verdict(meta):
    """the licence decision, taken on the API answer only"""
    short = strip_html(meta.get('LicenseShortName', {}).get('value')).lower()
    terms = strip_html(meta.get('UsageTerms', {}).get('value')).lower()
    blob = f'{short} {terms}'
    if any(b in blob for b in BAD_HINTS) and not any(o in short for o in ('cc0', 'cc-zero')):
        return False, f'refusé (licence « {short or terms or "?"} » : redistribution conditionnelle ou interdite)'
    if any(o in blob for o in OK_LICENCES):
        return True, f'accepté (« {short or terms} »)'
    return False, f'refusé (licence « {short or terms or "inconnue"} » non reconnue comme redistribuable)'


def candidates(query, limit=6):
    d = api(action='query', generator='search', gsrnamespace=6, gsrsearch=f'{query} filetype:audio',
            gsrlimit=limit, prop='imageinfo', iiprop='url|mime|size|extmetadata',
            iiextmetadatafilter='LicenseShortName|UsageTerms|Artist|LicenseUrl|Credit')
    out = []
    for p in (d.get('query', {}).get('pages') or []):
        ii = (p.get('imageinfo') or [{}])[0]
        meta = ii.get('extmetadata') or {}
        good, why = verdict(meta)
        out.append(dict(title=p['title'], mime=ii.get('mime'), bytes=ii.get('size'),
                        url=ii.get('url'), page=ii.get('descriptionurl'),
                        licence=strip_html(meta.get('LicenseShortName', {}).get('value')),
                        terms=strip_html(meta.get('UsageTerms', {}).get('value')),
                        author=strip_html(meta.get('Artist', {}).get('value')) or '(non crédité)',
                        licence_url=strip_html(meta.get('LicenseUrl', {}).get('value')),
                        accepted=good, verdict=why))
    return out


def survey(out_path=os.path.join('library', 'audio', 'SURVEY.json')):
    rows = {}
    for key, queries in QUERIES.items():
        found = []
        for q in queries:
            try: found += candidates(q)
            except Exception as e: print(f'  ! {key} / {q} : {e}')
            time.sleep(1.1)
        seen = set(); uniq = []
        for c in found:
            if c['title'] in seen: continue
            seen.add(c['title']); uniq.append(c)
        rows[key] = uniq
        ok = [c for c in uniq if c['accepted']]
        print(f"\n== {key} : {len(uniq)} candidats, {len(ok)} redistribuables")
        for c in uniq:
            print(f"   [{'OK ' if c['accepted'] else 'NON'}] {c['title'][:62]:62} {str(c['mime']):12} {c['licence'][:28]:28} {c['verdict'][:60]}")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f: json.dump(rows, f, ensure_ascii=False, indent=2)
    tot = sum(len(v) for v in rows.values()); ok = sum(1 for v in rows.values() for c in v if c['accepted'])
    print(f"\n{tot} candidats examinés, {ok} acceptables (CC0 / domaine public) -> {out_path}")
    print('Aucun fichier téléchargé à ce stade.')
    return rows


def slug(title):
    t = os.path.splitext(re.sub(r'^File:', '', title))[0]
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    return re.sub(r'_+', '_', re.sub(r'[^a-zA-Z0-9]+', '_', t)).strip('_').lower()[:48]


def info(title):
    """licence + download URL of ONE precise file, read before touching the bytes"""
    d = api(action='query', titles=title, prop='imageinfo', iiprop='url|mime|size|sha1|extmetadata',
            iiextmetadatafilter='LicenseShortName|UsageTerms|Artist|LicenseUrl|Credit')
    pages = d.get('query', {}).get('pages') or []
    if not pages or 'imageinfo' not in pages[0]: raise RuntimeError('fichier introuvable')
    ii = pages[0]['imageinfo'][0]; meta = ii.get('extmetadata') or {}
    good, why = verdict(meta)
    return dict(title=title, url=ii['url'], page=ii.get('descriptionurl'), mime=ii.get('mime'),
                bytes=ii.get('size'), sha1_commons=ii.get('sha1'),
                licence=strip_html(meta.get('LicenseShortName', {}).get('value')),
                terms=strip_html(meta.get('UsageTerms', {}).get('value')),
                licence_url=strip_html(meta.get('LicenseUrl', {}).get('value')),
                author=strip_html(meta.get('Artist', {}).get('value')) or '(non crédité sur Commons)',
                accepted=good, verdict=why)


def download(url, dst, tries=4):
    """Commons rate-limits (HTTP 429): back off and retry, and never re-download an existing file"""
    if os.path.exists(dst) and os.path.getsize(dst) > 1024:
        return hashlib.sha256(open(dst, 'rb').read()).hexdigest()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r, open(dst, 'wb') as f: f.write(r.read())
            return hashlib.sha256(open(dst, 'rb').read()).hexdigest()
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == tries - 1: raise
            wait = 30 * (k + 1); print(f'      429, nouvelle tentative dans {wait} s'); time.sleep(wait)


def _decode_av(path):
    """PyAV (bundled ffmpeg libraries), import-time only"""
    import av
    with av.open(path) as c:
        st = next(s for s in c.streams if s.type == 'audio')
        chunks = [f.to_ndarray().astype('float32') for f in c.decode(st)]
        sr = st.codec_context.sample_rate
    a = np.concatenate([x.mean(0) if x.ndim > 1 and x.shape[0] <= 8 else x.reshape(-1) for x in chunks])
    return a.astype('float32'), sr


def decode(path):
    """one-time decoding (ogg/flac/mp3/wav) -> mono float32 44100 Hz; soundfile is an import-time dependency only"""
    try:
        import soundfile as sf
        a, sr = sf.read(path, always_2d=True, dtype='float32')
        a = a.mean(1)
    except Exception:
        a, sr = _decode_av(path)         # Opus / exotic Ogg: libsndfile only does Vorbis
    if sr != L.SR: a = np.interp(np.arange(0, len(a), sr / L.SR), np.arange(len(a)), a).astype(np.float32)
    return np.ascontiguousarray(a, np.float32)


def best_slice(a, max_len, peak_db=-3.):
    """keep the loudest useful event of the recording, trimmed and levelled - nothing is synthesized"""
    w = int(.05 * L.SR)
    env = np.convolve(np.abs(a), np.ones(w, np.float32) / w, 'same')
    p = float(env.max()) if len(env) else 0.
    if p <= 1e-9: return a
    i = int(np.argmax(env)); s = i
    while s > 0 and env[s] > .02 * p: s -= 1
    e = min(len(a), s + int(max_len * L.SR))
    quiet = np.nonzero(env[i:e] < .015 * p)[0]
    if len(quiet): e = min(e, i + int(quiet[0]) + int(.25 * L.SR))
    out = L.align_attack(np.array(a[max(0, s - int(.01 * L.SR)):e], np.float32), pre=.004)
    out = L.edges(out, .0008, .02)
    pk = float(np.abs(out).max()) if len(out) else 0.
    if pk > 1e-9: out = out * (10 ** (peak_db / 20.) / pk)
    return out.astype(np.float32)


def fetch(dry=False):
    os.makedirs(os.path.join(L.ROOT, 'downloads'), exist_ok=True)
    log = []; added = {}
    for item in PLAN:
        key, title = item['event'], item['title']
        try: meta = info(title)
        except Exception as e:
            print(f'  ! {title} : {e}'); log.append(dict(title=title, event=key, status='erreur API', why=str(e)))
            time.sleep(PACE); continue
        print(f"[{'OK ' if meta['accepted'] else 'NON'}] {key:12} {title[:52]:52} {meta['licence'][:18]:18} {meta['verdict'][:46]}")
        if not meta['accepted']:
            log.append(dict(meta, event=key, status='refusé avant téléchargement')); time.sleep(PACE); continue
        if dry:
            log.append(dict(meta, event=key, status='accepté (dry run, rien téléchargé)')); time.sleep(PACE); continue
        raw = os.path.join(L.ROOT, 'downloads', slug(title) + (os.path.splitext(title)[1] or '.ogg'))
        try:
            sha = download(meta['url'], raw)
            a = decode(raw); cut = best_slice(a, float(item['max_len']))
            rel = f"sfx/{key}/{slug(title)}.wav"
            L.write_wav(os.path.join(L.ROOT, rel), cut)
            out_sha = hashlib.sha256(open(os.path.join(L.ROOT, rel), 'rb').read()).hexdigest()
        except Exception as e:
            print(f'    ! échec traitement : {e}'); log.append(dict(meta, event=key, status=f'échec traitement : {e}'))
            time.sleep(PACE); continue
        print(f"    -> {rel}  {len(cut) / L.SR:.2f} s  (source {len(a) / L.SR:.1f} s)")
        added.setdefault(key, []).append(dict(
            file=rel, weight=1.0, gain_db=0.0,
            credit=dict(kind='recording', source=f'Wikimedia Commons - {title}', url=meta['page'],
                        author=meta['author'], licence=meta['licence'], redistribute=True,
                        verified=(f"{time.strftime('%Y-%m-%d')} : licence lue via l'API Commons avant téléchargement "
                                  f"({meta['licence']} / {meta['terms']}) -> redistribution autorisée"),
                        licence_url=meta['licence_url'], sha256=out_sha, source_sha256=sha,
                        source_seconds=round(len(a) / L.SR, 2), kept_seconds=round(len(cut) / L.SR, 2))))
        log.append(dict(meta, event=key, status='téléchargé et converti', file=rel, sha256=out_sha))
        time.sleep(PACE)
    with open(os.path.join(L.ROOT, 'IMPORT_LOG.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(generated=time.strftime('%Y-%m-%d %H:%M'), user_agent=UA, allow_list=OK_LICENCES, entries=log),
                  f, ensure_ascii=False, indent=2)
    if not dry: merge_manifest(added)
    return added


def merge_manifest(added):
    """real recordings take over the events they cover: the synthetic placeholders of those events leave the manifest"""
    path = os.path.join(L.ROOT, 'manifest.json')
    man = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'version': 1, 'events': {}}
    for key, variants in added.items():
        ev = man['events'].setdefault(key, dict(description=S.SFX_DESCRIPTIONS.get(key, ''), loop=False, variants=[]))
        keep = [v for v in ev.get('variants', []) if (v.get('credit') or {}).get('kind') == 'recording'
                and v['file'] not in {x['file'] for x in variants}]
        ev['variants'] = keep + variants
        ev['align'] = 'transient' if key in L.IMPULSIVE_EVENTS else 'attack'
        ev['pitch_jitter'] = min(60, int(ev.get('pitch_jitter', 60)))        # real material: gentle variation only
        ev['gain_jitter_db'] = min(1.5, float(ev.get('gain_jitter_db', 1.5)))
    with open(path, 'w', encoding='utf-8') as f: json.dump(man, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nmanifeste mis à jour : {sum(len(v) for v in added.values())} enregistrements réels sur {len(added)} événements")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'survey'
    if cmd == 'survey': survey()
    elif cmd == 'fetch': fetch('--dry' in sys.argv)
    else: print(__doc__)
