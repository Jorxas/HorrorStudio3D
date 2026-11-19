"""Quick checks of the publication pack (seconds, no API, no rendering, nothing written in projects/).

Checks that for ONE episode the YouTube Shorts title/description and the TikTok caption are distinct and relevant,
that the episode number and the series continuity are carried, that the 2 or 3 choices come from the episode only,
that the inherited clickbait formulas are stripped, and that the former keys of metadata.json are untouched.

  python tools/check_publication.py          # exit 1 on any failure
  python tools/check_publication.py --json   # also print the pack of the two example episodes
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

# ---------------------------------------------------------------- example series (2 episodes, the 2 engines)
PIXEL = {'project': {'name': "L'Étage 0 - Partie 4", 'style': 'pixel3d', 'series': "L'Étage 0 n'existe pas",
                     'part_label': 'PARTIE 4', 'previous_choice': 'B', 'previous_choice_text': 'REFERMER LES PORTES'},
         'episode': {'style': 'pixel3d', 'hud': {'title': ["L'ÉTAGE 0", "N'EXISTE PAS"], 'part': 'PARTIE 4'},
                     'summary': "Ton double t'attend devant l'ascenseur de l'étage 0. Une seule version peut sortir.",
                     'shots': [{'lines': [0, 2], 'ui': {'recap': {'title': 'TON CHOIX :', 'letter': 'B'}}},
                               {'lines': [3, 8]},
                               {'lines': [9, 11], 'ui': {'choice': {'title': 'QUE FAIS-TU ?', 'A': ['SORTIR', "L'AFFRONTER"],
                                                                    'B': ['REFERMER', 'LES PORTES']}}},
                               {'lines': [12, 12], 'ui': {'endcard': {'headline': 'A OU B ?'}}}]}}
CONSOLE = {'project': {'name': 'Ne mets pas pause - Niveau 2', 'style': 'console', 'series': 'NE METS PAS PAUSE',
                       'part_label': 'NIVEAU 2'},
           'episode': {'style': 'console', 'hud': {'series': 'NE METS PAS PAUSE', 'level': 'NIVEAU 2'},
                       'summary': "La console connaît ton prénom et la voix derrière la porte aussi.",
                       'shots': [{'lines': [0, 5]},
                                 {'lines': [6, 9], 'ui': {'choice': {'title': 'QUI CROIS-TU ?', 'A': 'LA CONSOLE',
                                                                     'B': 'LA VOIX', 'C': 'NI LES DEUX'}}}]}}
# what the heuristic director writes today (horror branch of director.base_metadata), with one lying formula added
BASE = {'titles': ["L'Étage 0 n'existe pas - PARTIE 4 : ne regarde pas derrière toi",
                   "L'Étage 0 n'existe pas PARTIE 4 | Histoire d'horreur interactive (choisis A ou B)",
                   "Tu n'aurais jamais dû faire ça... (histoire vraie)"],
        'description': "Ton double t'attend.\n\nA ou B ? Vote en commentaire !",
        'hashtags': ['horreur', 'histoiredhorreur', 'creepypasta', 'choisistonhistoire', 'histoireinteractive',
                     'pixelart', 'indiehorror', 'fyp', 'shorts'],
        'thumbnail_text': ['LA PORTE', 'NE REGARDE', 'PAS'], 'tags': ['horreur', 'histoire', 'creepypasta']}

def pack_checks():
    from hstudio import publish
    p = publish.pack(PIXEL['project'], PIXEL['episode'], BASE)
    yt, tk = p['youtube_shorts'], p['tiktok']
    check('numéro d\'épisode lu dans « PARTIE 4 »', p['episode_number'] == 4, str(p['episode_number']))
    check('série reconnue', p['series'] == "L'Étage 0 n'existe pas", p['series'])
    check('2 choix repris de ui.choice', [c['letter'] for c in p['choices']] == ['A', 'B'], str(p['choices']))
    check('texte du choix A assemblé', p['choices'][0]['text'] == "SORTIR L'AFFRONTER", str(p['choices'][0]))
    check('question du vote reprise', p['vote_line'] == 'QUE FAIS-TU ? A ou B ?', p['vote_line'])
    check('choix précédent (continuité de série)', p['previous_choice'] == {'letter': 'B', 'text': 'REFERMER LES PORTES'}, str(p['previous_choice']))
    check('continuité écrite dans la description YouTube', 'choisi B' in yt['description'] and 'REFERMER LES PORTES' in yt['description'])
    check('titre YouTube ≤ 70 caractères', len(yt['title']) <= 70, f"{len(yt['title'])} : {yt['title']}")
    check('titre YouTube : série + numéro', 'Ép. 4' in yt['title'] and "L'Étage 0" in yt['title'], yt['title'])
    check('titre YouTube sans doublon de « PARTIE 4 »', 'PARTIE 4' not in yt['title'], yt['title'])
    check('légende TikTok ≠ titre YouTube', tk['caption'] != yt['title'])
    check('légende TikTok ≠ description YouTube', tk['caption'] != yt['description'])
    check('légende TikTok porte le numéro d\'épisode', 'Ép. 4' in tk['caption'], tk['caption'])
    check('légende TikTok : hashtags dans la légende', '#' in tk['caption'] and 'pourtoi' in tk['hashtags'])
    check('légende TikTok : les deux options lisibles', 'A SORTIR' in tk['caption'] and 'B REFERMER' in tk['caption'], tk['caption'])
    check('pas de #shorts sur TikTok', 'shorts' not in tk['hashtags'], str(tk['hashtags']))
    check('#shorts présent et premier sur YouTube', yt['hashtags'][0] == 'shorts', str(yt['hashtags']))
    check('hashtags YouTube ≤ 6, TikTok ≤ 8', len(yt['hashtags']) <= 6 and len(tk['hashtags']) <= 8)
    check('hashtag de série ajouté', 'letage0nexistepas' in yt['hashtags'] or 'letage0nexistepas' in tk['hashtags'], str(yt['hashtags']))
    check('titre passe-partout du réalisateur offline remplacé par le résumé de l’épisode',
          p['hook'].startswith('Ton double') and 'ne regarde pas' not in p['hook'], p['hook'])
    specific = publish.pack(PIXEL['project'], PIXEL['episode'], dict(BASE, titles=["L'ascenseur descend sous l'étage 0"]))
    check('titre spécifique (écrit par un LLM) conservé tel quel',
          specific['hook'] == "L'ascenseur descend sous l'étage 0", specific['hook'])
    check('clickbait mensonger retiré du hook', 'histoire vraie' not in (p['hook'] + yt['title'] + tk['caption']).lower(), p['hook'])
    check('champ tags YouTube seulement', 'tags' in yt and 'tags' not in tk)
    check('miniature/cover existantes réutilisées', (yt['thumbnail'], yt['cover'], tk['cover']) == ('thumbnail_16x9.jpg', 'cover_9x16.jpg', 'cover_9x16.jpg'))

def console_and_edge_checks():
    from hstudio import publish
    c = publish.pack(CONSOLE['project'], CONSOLE['episode'], dict(BASE, titles=['NE METS PAS PAUSE NIVEAU 2 : qui croire ?'], hashtags=['horreur', 'console', 'retrogaming', 'fyp']))
    check('CONSOLE 2D : style porté dans le pack', c['style'] == 'console', c['style'])
    check('CONSOLE 2D : numéro lu dans « NIVEAU 2 »', c['episode_number'] == 2, str(c['episode_number']))
    check('3 choix acceptés', [x['letter'] for x in c['choices']] == ['A', 'B', 'C'], str(c['choices']))
    check('vote à 3 options formulé', c['vote_line'] == 'QUI CROIS-TU ? A, B ou C ?', c['vote_line'])
    check('CONSOLE : pas de choix précédent inventé', c['previous_choice'] is None, str(c['previous_choice']))
    check('légendes différentes entre les deux épisodes', c['tiktok']['caption'] != publish.pack(PIXEL['project'], PIXEL['episode'], BASE)['tiktok']['caption'])
    # non-interactive episode: no vote promised
    flat = publish.pack({'style': 'pixel3d', 'series': 'Histoire', 'part_label': ''}, {'summary': 'Une nuit, seul.', 'shots': [{'lines': [0, 1]}]}, {})
    check('épisode sans choix : non interactif', flat['interactive'] is False and flat['choices'] == [])
    check('épisode sans choix : aucun « A ou B ? » promis', 'A ou B' not in flat['youtube_shorts']['description'] and 'commente' not in flat['tiktok']['caption'])
    check('épisode sans choix : titre quand même produit', len(flat['youtube_shorts']['title']) > 0, flat['youtube_shorts']['title'])
    # a single written option is not a vote
    one = publish.pack({}, {'shots': [{'ui': {'choice': {'title': 'ET ?', 'A': 'RESTER'}}}]}, {})
    check('un seul choix écrit n\'est pas un vote', one['choices'] == [] and one['interactive'] is False, str(one['choices']))
    # empty / partial input must not raise
    empty = publish.pack(None, None, None)
    check('entrée vide tolérée', isinstance(empty.get('youtube_shorts', {}).get('title'), str))
    opts = publish.pack({}, {'shots': [{'ui': {'choice': {'options': ['OUVRIR', 'FUIR']}}}]}, {})
    check('forme « options » tolérée', [x['letter'] for x in opts['choices']] == ['A', 'B'], str(opts['choices']))
    check('pack sérialisable en JSON', isinstance(json.dumps(c, ensure_ascii=False), str))
    txt = publish.as_text(c)
    check('fiche lisible : un bloc par plateforme', '--- YOUTUBE SHORTS ---' in txt and '--- TIKTOK ---' in txt)
    check('fiche lisible : légende TikTok et titre YouTube présents',
          c['tiktok']['caption'] in txt and c['youtube_shorts']['title'] in txt)
    check('fiche lisible : publication manuelle annoncée', 'rien n’est envoyé automatiquement' in txt)
    check('fiche lisible : pack vide toléré', isinstance(publish.as_text({}), str))

def fixture_checks():
    """tests/fixtures/publication_pack.json feeds the frontend check: it must stay in sync with the code"""
    from hstudio import publish
    fx = json.load(open(os.path.join(ROOT, 'tests', 'fixtures', 'publication_pack.json'), encoding='utf-8'))
    ep = json.load(open(os.path.join(ROOT, 'examples', 'ne_mets_pas_pause_demo', 'episode.json'), encoding='utf-8'))
    fresh = publish.pack(fx['project'], ep, fx['base_metadata'])
    check('fixture du pack à jour (sinon relancer la génération)', fresh == fx['platforms'],
          'tests/fixtures/publication_pack.json ne correspond plus à publish.pack')
    check('fixture : épisode réel interactif A/B', [c['letter'] for c in fx['platforms']['choices']] == ['A', 'B'])

def thumbnail_checks():
    """the badge and the vote strip of the miniature/cover (logic only, no rendering here)"""
    from hstudio import thumbnail
    check('miniature : bandeau de vote A/B', thumbnail._vote_badge(PIXEL['episode']) == 'A OU B ?', thumbnail._vote_badge(PIXEL['episode']))
    check('miniature : bandeau de vote A/B/C', thumbnail._vote_badge(CONSOLE['episode']) == 'A, B OU C ?', thumbnail._vote_badge(CONSOLE['episode']))
    check('miniature : aucun bandeau sans choix écrit', thumbnail._vote_badge({'shots': [{'lines': [0, 1]}]}) == '')
    check('miniature : un seul choix écrit ne fait pas de vote', thumbnail._vote_badge({'shots': [{'ui': {'choice': {'A': 'RESTER'}}}]}) == '')
    check('miniature : badge = libellé du propriétaire', thumbnail._part_badge(PIXEL['project'], PIXEL['episode'], 'A OU B ?') == 'PARTIE 4')
    check('miniature : badge repris de l’épisode si absent du projet',
          thumbnail._part_badge({}, CONSOLE['episode'], 'A, B OU C ?') == 'NIVEAU 2', thumbnail._part_badge({}, CONSOLE['episode'], 'A, B OU C ?'))
    check('miniature : épisode à choix jamais annoncé « histoire complète »',
          thumbnail._part_badge({}, {'shots': [{'ui': {'choice': {'A': 'X', 'B': 'Y'}}}]}, 'A OU B ?') == 'À SUIVRE')
    check('miniature : épisode sans choix reste « histoire complète »', thumbnail._part_badge({}, {'shots': []}, '') == 'HISTOIRE COMPLÈTE')

def compat_checks():
    """the former keys of metadata.json keep their value: only `platforms` is added"""
    from hstudio import director
    settings = {'director': 'heuristic'}
    lines = [{'text': 'Il y a une porte.'}, {'text': 'Choix A : ouvrir'}, {'text': 'Choix B : fuir'}]
    base = director.base_metadata(dict(PIXEL['project']), lines, dict(PIXEL['episode']), settings, log=lambda *a: None)
    md = director.metadata(dict(PIXEL['project']), lines, dict(PIXEL['episode']), settings, log=lambda *a: None)
    check('aucune clé historique perdue', set(base) <= set(md), str(set(base) - set(md)))
    check('clés historiques inchangées', all(md[k] == base[k] for k in base), str([k for k in base if md[k] != base[k]]))
    check('seule « platforms » est ajoutée', set(md) - set(base) == {'platforms'}, str(set(md) - set(base)))
    check('thumbnail_text toujours utilisable par thumbnail.py', isinstance(md.get('thumbnail_text'), list) and len(md['thumbnail_text']) <= 3)
    check('platforms contient les deux plateformes', {'youtube_shorts', 'tiktok'} <= set(md['platforms']))
    check('director.metadata ne lève rien sans épisode', isinstance(director.metadata({}, [], {}, settings, log=lambda *a: None), dict))

if __name__ == '__main__':
    pack_checks(); console_and_edge_checks(); fixture_checks(); thumbnail_checks(); compat_checks()
    if '--json' in sys.argv:
        from hstudio import publish
        for n, s in (('pixel3d', PIXEL), ('console', CONSOLE)):
            print(f'\n--- {n} ---\n' + json.dumps(publish.pack(s['project'], s['episode'], BASE), ensure_ascii=False, indent=1))
    print(f"\n{'ÉCHECS : ' + ', '.join(FAIL) if FAIL else 'Tout est OK.'}")
    sys.exit(1 if FAIL else 0)
