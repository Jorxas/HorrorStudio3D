"""Un fichier `.mp4` sur le disque n'est pas une vidéo. Ce module est la différence entre les deux.

Il existe à cause d'une panne réellement payée deux fois : un encodage tué en cours de route laisse un MP4 de
quelques dizaines d'octets — l'en-tête `ftyp`, un `mdat` vide, **et pas de `moov`**. Rien ne l'annonce :

- `step_render` ne regardait que le code de retour de ffmpeg, puis la taille du fichier ;
- `oneclick` considérait l'étape « rendu » faite parce qu'un `.mp4` portait le bon nom ;
- le contrôle qualité mesure la mise en scène **avant** le rendu : il a donné 92/100 à un fichier de 48 octets.

Les trois ensemble transforment un encodage interrompu en « parcours terminé », et cassent justement la reprise.

Trois niveaux de vérification, du moins cher au plus cher :

- `structure()` : la chaîne d'atomes lue à la main, sans aucun sous-processus. C'est le niveau que l'interface
  peut se permettre à chaque sondage. Il attrape exactement la panne ci-dessus (`moov` absent, `mdat` vide) ;
- `probe()` : `ffprobe`, pour les codecs, la taille d'image, la durée, la piste audio ;
- `decodes()` : un décodage **complet** par ffmpeg vers `null`. Seul lui prouve qu'on peut regarder le fichier
  jusqu'au bout ; il coûte du temps réel, donc il est réservé à la fin d'un rendu et aux outils de preuve.

Aucun réseau, aucune clé, aucun coût. Rien n'est jamais supprimé : `quarantine()` **renomme** un fichier douteux
pour qu'il ne puisse plus passer pour un artefact valide, et rend le nouveau chemin.
"""
import os, json, struct, subprocess, time

# en dessous, aucun MP4 ne peut contenir un flux regardable : le fichier tronqué mesuré faisait 48 octets
MIN_SIZE = 4096


def atoms(path, limit=4096):
    """La chaîne d'atomes de premier niveau : [(type, taille, offset)]. Lecture seule, aucun sous-processus.

    `limit` borne le nombre d'atomes lus : un fichier abîmé peut annoncer n'importe quoi, on ne boucle pas pour
    lui. Un atome de taille 0 s'étend jusqu'à la fin du fichier (légal, c'est le dernier)."""
    out, size = [], os.path.getsize(path)
    with open(path, 'rb') as f:
        off = 0
        while off < size and len(out) < limit:
            head = f.read(8)
            if len(head) < 8: break                        # queue tronquée : l'atome annoncé n'existe pas
            n, typ = struct.unpack('>I', head[:4])[0], head[4:8]
            adv = 8
            if n == 1:                                     # taille 64 bits, juste après le type
                ext = f.read(8)
                if len(ext) < 8: break
                n, adv = struct.unpack('>Q', ext)[0], 16
            elif n == 0:
                n = size - off                             # « jusqu'à la fin du fichier »
            if n < adv: break                              # taille impossible : on arrête plutôt que reculer
            out.append((typ.decode('latin-1'), int(n), off))
            off += n
            f.seek(off)
    return out


def structure(path):
    """Le verdict pas cher : ce MP4 a-t-il de quoi être lu ? -> {'ok': bool, 'reason': str, ...}

    `moov` est la table des matières : sans elle aucun lecteur ne sait quoi décoder, et c'est précisément ce
    qu'un encodeur écrit **en dernier**. Son absence est la signature d'un encodage interrompu."""
    r = {'ok': False, 'reason': '', 'size': 0, 'atoms': [], 'moov': False, 'mdat': 0, 'truncated': False}
    if not os.path.isfile(path):
        r['reason'] = "le fichier n'existe pas"; return r
    r['size'] = os.path.getsize(path)
    if r['size'] < MIN_SIZE:
        r['reason'] = 'fichier de ' + str(r['size']) + ' octets : trop petit pour contenir une vidéo'
        # on continue quand même la lecture des atomes : elle nomme la panne
    try: found = atoms(path)
    except Exception as e:
        r['reason'] = r['reason'] or ("chaîne d'atomes illisible : " + str(e)); return r
    r['atoms'] = [t for t, _, _ in found]
    r['moov'] = any(t == 'moov' for t, _, _ in found)
    r['mdat'] = sum(n for t, n, _ in found if t == 'mdat')
    covered = sum(n for _, n, _ in found)
    r['truncated'] = bool(found) and covered > r['size']
    if not found:
        r['reason'] = r['reason'] or "aucun atome MP4 : ce n'est pas un MP4"
    elif found[0][0] != 'ftyp':
        r['reason'] = r['reason'] or 'ne commence pas par « ftyp »'
    elif not r['moov']:
        r['reason'] = ("pas d'atome « moov » : encodage interrompu, le fichier n'est pas lisible "
                       '(la panne du MP4 tué en cours de route)')
    elif r['mdat'] <= 8:
        r['reason'] = r['reason'] or 'atome « mdat » vide : aucune image encodée'
    elif r['truncated']:
        r['reason'] = 'fichier tronqué : les atomes annoncent ' + str(covered) + ' octets pour ' + str(r['size'])
    elif r['size'] >= MIN_SIZE:
        r['ok'] = True
    return r


def playable(path):
    """Le raccourci que l'interface et la reprise utilisent : vrai si le fichier a de quoi être lu."""
    try: return structure(path)['ok']
    except Exception: return False


def probe(path):
    """`ffprobe` -> dict des flux et du format, ou None si ffprobe refuse le fichier."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path],
                       capture_output=True, text=True)
    if r.returncode: return None
    try: return json.loads(r.stdout)
    except Exception: return None


def decodes(path):
    """Décodage **complet** vers `null`, pas une lecture d'en-tête -> (ok, première erreur).

    C'est la seule preuve qu'on peut regarder le fichier en entier. Coûteux : réservé à la fin d'un rendu."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    return (r.returncode == 0 and not r.stderr.strip()), (r.stderr or '').strip()[:300]


def describe(path, want=None, full=False):
    """Le verdict complet d'un rendu : structure, puis ffprobe, puis (si `full`) le décodage entier.

    `want` = (largeur, hauteur) attendue ; une image qui n'est pas au format demandé est un échec, pas un détail.
    Retourne un dict toujours de la même forme, `ok` et `reason` compris, pour qu'un journal puisse le garder."""
    v = {'path': path, 'ok': False, 'reason': '', 'size': 0, 'duration': 0., 'video': '', 'audio': '',
         'width': 0, 'height': 0, 'fps': 0., 'channels': 0, 'sample_rate': 0, 'moov': False, 'decoded': None}
    st = structure(path)
    v['size'] = st['size']; v['moov'] = st['moov']
    if not st['ok']:
        v['reason'] = st['reason']; return v
    info = probe(path)
    if not info:
        v['reason'] = 'ffprobe refuse le fichier (structure pourtant plausible)'; return v
    streams = info.get('streams') or []
    vs = next((s for s in streams if s.get('codec_type') == 'video'), {})
    aud = next((s for s in streams if s.get('codec_type') == 'audio'), {})
    try: v['duration'] = float((info.get('format') or {}).get('duration') or 0)
    except (TypeError, ValueError): v['duration'] = 0.
    v['video'] = vs.get('codec_name') or ''
    v['width'], v['height'] = int(vs.get('width') or 0), int(vs.get('height') or 0)
    num, _, den = (vs.get('avg_frame_rate') or '0/1').partition('/')
    try: v['fps'] = round(float(num) / float(den or 1), 3)
    except (TypeError, ValueError, ZeroDivisionError): v['fps'] = 0.
    v['audio'] = aud.get('codec_name') or ''
    v['channels'] = int(aud.get('channels') or 0)
    try: v['sample_rate'] = int(aud.get('sample_rate') or 0)
    except (TypeError, ValueError): v['sample_rate'] = 0

    if not v['video']: v['reason'] = 'aucune piste vidéo'
    elif v['duration'] <= 0: v['reason'] = 'durée nulle : aucune image utilisable'
    elif want and (v['width'], v['height']) != tuple(want):
        v['reason'] = ('format ' + str(v['width']) + 'x' + str(v['height']) + ' au lieu de '
                       + str(want[0]) + 'x' + str(want[1]))
    if v['reason']: return v
    if full:
        ok, err = decodes(path)
        v['decoded'] = ok
        if not ok:
            v['reason'] = 'le décodage complet signale : ' + (err or 'une erreur sans message'); return v
    v['ok'] = True
    return v


def summary(v):
    """Une ligne lisible pour le journal du studio, en français, sans jargon inutile."""
    if not v.get('ok'):
        return 'Rendu refusé (' + str(v.get('size', 0)) + ' o) : ' + (v.get('reason') or 'raison inconnue')
    return ('Vidéo vérifiée : ' + v['video'] + ' ' + str(v['width']) + 'x' + str(v['height']) + ', '
            + ('%.3f' % v['fps']) + ' i/s, ' + ('%.2f' % v['duration']) + ' s, '
            + (v['audio'] + ' ' + str(v['channels']) + ' canaux ' + str(v['sample_rate']) + ' Hz' if v['audio'] else 'sans audio')
            + ', ' + ('%.1f' % (v['size'] / 1e6)) + ' Mo'
            + (', décodage complet sans erreur' if v.get('decoded') else ''))


def quarantine(path, reason=''):
    """Écarte un rendu douteux **sans le supprimer** : il est renommé, donc il ne peut plus passer pour valide.

    Rien de ce que le propriétaire a produit n'est effacé : le fichier reste à côté, sous un nom horodaté, avec
    la raison dans un `.txt` voisin. Rend le nouveau chemin, ou l'ancien si le renommage est impossible."""
    if not os.path.exists(path): return path
    base, ext = os.path.splitext(path)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    dest, k = base + '.ECARTE-' + stamp + ext, 0
    while os.path.exists(dest):
        k += 1; dest = base + '.ECARTE-' + stamp + '-' + str(k) + ext
    try: os.replace(path, dest)
    except OSError: return path
    try:
        with open(dest + '.txt', 'w', encoding='utf-8') as f:
            f.write('Rendu écarté le ' + time.strftime('%Y-%m-%d %H:%M:%S') + '\n'
                    "Fichier d'origine : " + path + '\n'
                    'Raison : ' + (reason or 'non précisée') + '\n\n'
                    "Ce fichier n'est pas lisible. Il est conservé pour examen, pas supprimé.\n"
                    'Relancer le rendu refabrique le bon fichier sous son nom normal.\n')
    except OSError: pass
    return dest
