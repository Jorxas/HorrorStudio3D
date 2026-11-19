"""Offline check of the voice casting (hstudio/voices.py): one voice_id per character and a distinct narrator.

No ElevenLabs call, no key, no cost: the provider, the duration reader and the concatenation are fake and injected
into voices.synthesize_cast. The character library is redirected to a temporary folder, so library/ is not touched.

    python tools/check_voices.py
"""
import json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hstudio import align, voices as V
from hstudio.acting import cast as CAST
from hstudio.engines.common import norm

KEY = 'FAUSSE-CLE-AUCUN-APPEL'
SEC_PER_CHAR = .05          # the fake provider: 50 ms of audio per character, 100 bytes per character
FAILED = []


def check(ok, label, detail=''):
    print(('  OK    ' if ok else '  ECHEC ') + label + (f'   [{detail}]' if detail and not ok else ''))
    if not ok: FAILED.append(label)


# ----------------------------------------------------------------- the fakes
class Provider:
    """stands in for tts.request_tts: records what voice_id receives what text, returns silence + its timings"""
    def __init__(self): self.calls = []

    def request(self, key, voice_id, text, model_id='eleven_v3', voice_settings=None):
        assert key == KEY, 'the key must be passed through to the provider'
        self.calls.append({'voice_id': voice_id, 'text': text, 'model': model_id})
        n = len(text)
        al = {'characters': list(text),
              'character_start_times_seconds': [round(i * SEC_PER_CHAR, 4) for i in range(n)],
              'character_end_times_seconds': [round((i + 1) * SEC_PER_CHAR, 4) for i in range(n)]}
        return b'\0' * (n * 100), al


def fake_duration(path):
    return os.path.getsize(path) / (100 / SEC_PER_CHAR)


def make_concat(order):
    def concat(parts, out_mp3, workdir):
        order[:] = [os.path.basename(p) for p in parts]
        open(out_mp3, 'w', encoding='utf-8').write('\n'.join(order))
    return concat


# ----------------------------------------------------------------- the fixture
LINES = [
    {'speaker': None, 'tts': "La porte de l'etage zero ne s'ouvre jamais la nuit."},
    {'speaker': None, 'tts': "Pourtant ce soir, elle est entrouverte."},
    {'speaker': 'lea', 'tts': "Tu entends ce *bruit*, Tom ?"},
    {'speaker': 'tom', 'tts': "C'est juste la chaudiere."},
    {'speaker': 'lea', 'tts': "Non. Ca vient d'en dessous."},
    {'speaker': 'lea', 'tts': "Regarde la lumiere."},
    {'speaker': None, 'tts': "Ils descendirent une marche de plus."},
    {'speaker': 'tom', 'tts': "Attends-moi."},
]
for l in LINES: l['text'] = l['tts'].replace('*', '')

NARR_ID, LEA_ID, TOM_ID, GLOBAL_ID = 'VID-NARRATEUR', 'VID-LEA', 'VID-TOM', 'VID-GLOBALE'


def write_library(tmp, with_voices=True):
    d = os.path.join(tmp, 'characters'); os.makedirs(d, exist_ok=True)
    for cid, name, vid in (('lea', 'Léa', LEA_ID), ('tom', 'Tom', 'VID-TOM-BIBLIO')):
        c = {'id': cid, 'name': name, 'voice': {'draft': 'woman', 'elevenlabs_voice_id': vid if with_voices else ''}}
        json.dump(c, open(os.path.join(d, f'{cid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    CAST.CHAR_DIR = d


def run(lines, voices, workdir, out, provider=None):
    provider = provider or Provider()
    order = []
    al = V.synthesize_cast(KEY, lines, voices, out, workdir, model_id='eleven_v3', log=lambda *a: None,
                           request=provider.request, duration=fake_duration, concat=make_concat(order))
    return provider, al, order


def main():
    tmp = tempfile.mkdtemp(prefix='hs_voices_')
    old_dir = CAST.CHAR_DIR
    try:
        write_library(tmp)
        # the project casts Tom himself (by name, with an accent-free key) and the narrator comes from the settings
        meta = {'cast': ['lea', 'tom'], 'voices': {'Tom': TOM_ID}}
        settings = {'elevenlabs_api_key': KEY, 'elevenlabs_voice_id': GLOBAL_ID, 'elevenlabs_narrator_voice_id': NARR_ID}

        print('1. resolution des voix (projet > cast > bibliotheque > narrateur > voix globale)')
        speakers = V.speakers_of(LINES)
        check(speakers == [V.NARRATOR, 'lea', 'tom'], 'locuteurs dans l\'ordre d\'apparition', speakers)
        vo = V.resolve(meta, settings, speakers)
        check(vo['lea']['voice_id'] == LEA_ID and vo['lea']['source'] == 'bibliothèque', 'Lea : voix heritee de la bibliotheque', vo['lea'])
        check(vo['tom']['voice_id'] == TOM_ID and vo['tom']['source'] == 'projet', 'Tom : voix du projet prioritaire sur la bibliotheque', vo['tom'])
        check(vo[V.NARRATOR]['voice_id'] == NARR_ID, 'narrateur : voice_id distinct des personnages', vo[V.NARRATOR])
        ids = {v['voice_id'] for v in vo.values()}
        check(len(ids) == 3, '3 voice_ids differents pour 2 personnages + narrateur', ids)
        check(vo['lea']['name'] == 'Léa' and vo[V.NARRATOR]['name'] == V.NARRATOR_NAME, 'noms affiches (accents de la bibliotheque)',
              (vo['lea']['name'], vo[V.NARRATOR]['name']))

        print('2. ordre des repliques et regroupement')
        segs = V.plan(LINES, vo)
        got = [(s['voice_id'], tuple(s['lines'])) for s in segs]
        want = [(NARR_ID, (0, 1)), (LEA_ID, (2,)), (TOM_ID, (3,)), (LEA_ID, (4, 5)), (NARR_ID, (6,)), (TOM_ID, (7,))]
        check(got == want, 'segments : repliques consecutives de meme voix groupees, ordre du script', got)
        flat = [i for s in segs for i in s['lines']]
        check(flat == list(range(len(LINES))), 'aucune replique perdue ni reordonnee', flat)

        print('3. envoi au provider simule')
        w1 = os.path.join(tmp, 'work1')
        p1, al, order = run(LINES, vo, w1, os.path.join(tmp, 'voice1.mp3'))
        check(len(p1.calls) == len(segs), 'une requete par segment', len(p1.calls))
        check([c['voice_id'] for c in p1.calls] == [s['voice_id'] for s in segs], 'voice_id envoye pour chaque segment, dans l\'ordre',
              [c['voice_id'] for c in p1.calls])
        check(len({c['voice_id'] for c in p1.calls}) == 3, '3 voice_ids differents recus par le provider',
              sorted({c['voice_id'] for c in p1.calls}))
        check([c['text'] for c in p1.calls] == ['\n\n'.join(s['texts']) for s in segs], 'texte de chaque segment (sans les *)')
        check(all('*' not in c['text'] for c in p1.calls), 'les asterisques de mise en scene ne partent pas au provider')
        check(order == [s['file'] for s in al['segments']], 'concatenation dans l\'ordre des segments', order)

        print('4. horodatage continu (longueur audio cumulee)')
        off = 0.; ok_off = True; ok_len = True
        for s, seg in zip(segs, al['segments']):
            d = len('\n\n'.join(s['texts'])) * SEC_PER_CHAR
            ok_off = ok_off and abs(seg['start'] - off) < 1e-3
            ok_len = ok_len and abs((seg['end'] - seg['start']) - d) < 1e-3
            off += d
        check(ok_off, 'chaque segment demarre a la fin du precedent')
        check(ok_len, 'duree de chaque segment = duree reelle de sa partie audio')
        check(abs(max(al['ends']) - off) < 1e-3, 'fin du dernier horodatage = duree totale', (max(al['ends']), off))
        check(all(b >= a - 1e-6 for a, b in zip(al['starts'], al['starts'][1:])), 'horodatages croissants sur toute la piste')
        words = align.words_from_alignment(al)
        want_words = [t for t in ' '.join(l['text'] for l in LINES).split() if norm(t)]   # align drops pure punctuation
        check(len(words) == len(want_words), 'tous les mots du script sont relus par align', (len(words), len(want_words)))
        matched = align.match_lines([dict(l) for l in LINES], words)
        check(all(matched[i]['start'] <= matched[i + 1]['start'] + 1e-6 for i in range(len(matched) - 1)),
              'align.match_lines : repliques calees dans l\'ordre')

        print('5. cache')
        p2, al2, _ = run(LINES, vo, w1, os.path.join(tmp, 'voice1.mp3'))
        check(p2.calls == [], 'deuxieme passe : aucune requete, tout vient du cache', len(p2.calls))
        check(al2['starts'] == al['starts'] and al2['ends'] == al['ends'], 'alignement identique depuis le cache')
        vo_tom = dict(vo, tom=dict(vo['tom'], voice_id='VID-TOM-V2'))
        p3, al3, _ = run(LINES, vo_tom, w1, os.path.join(tmp, 'voice1.mp3'))
        check([c['voice_id'] for c in p3.calls] == ['VID-TOM-V2', 'VID-TOM-V2'],
              'changer la voix de Tom ne resynthetise que Tom (cache indexe par voice_id)', [c['voice_id'] for c in p3.calls])

        print('6. repli mono-voix (compatibilite)')
        write_library(tmp, with_voices=False)
        vo_mono = V.resolve({'cast': ['lea', 'tom']}, {'elevenlabs_voice_id': GLOBAL_ID}, speakers)
        check({v['voice_id'] for v in vo_mono.values()} == {GLOBAL_ID}, 'sans voix castee : tout le monde sur la voix globale')
        p4, al4, order4 = run(LINES, vo_mono, os.path.join(tmp, 'work2'), os.path.join(tmp, 'voice2.mp3'))
        check(len(p4.calls) == 1 and p4.calls[0]['voice_id'] == GLOBAL_ID, 'une seule requete, comme avant la mise en voix multiple',
              [c['voice_id'] for c in p4.calls])
        check(len(order4) == 1 and len(al4['segments']) == 1, 'un seul morceau audio concatene')
    finally:
        CAST.CHAR_DIR = old_dir
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print(f'{len(FAILED)} echec(s) : ' + ' | '.join(FAILED)); return 1
    print('Tout OK (aucun appel ElevenLabs, aucun cout).'); return 0


if __name__ == '__main__':
    sys.exit(main())
