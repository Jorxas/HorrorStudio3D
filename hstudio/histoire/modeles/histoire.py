r"""MISE EN SCÈNE de l'histoire (dossier {{DOSSIER}}) — écrite par l'IA, lue par le kit du moteur.

    python -m hstudio.histoire construire "{{DOSSIER}}"      (puis apercu, verifier, rendre, mixer, livrer)

Guide complet : {{MOTEUR}}\docs\GUIDE_HISTOIRE_POUR_IA.md (LIS-LE AVANT D'ÉCRIRE).
PHRASES.md donne, pour chaque phrase dite, son numéro, son début et sa fin en secondes.
Tous les temps écrits ici sont ABSOLUS (secondes du film). Repère : x vers la droite de l'image quand on regarde vers +z,
y vers le haut ; yaw = atan2(dx, dz) : 0 regarde vers +z, PI/2 vers +x, PI vers -z. Rien d'aléatoire.

CE FICHIER EST UN MODÈLE QUI TOURNE TEL QUEL (un plan par phrase, un personnage dans un couloir) pour vérifier la chaîne.
Il N'EST PAS une mise en scène : remplace build() par la tienne, moment par moment (voir le guide, § 5)."""
from hstudio.histoire.lib import *          # noqa: F401,F403  (ls, le, L, K, C, CUT, head, toward, SIZES, PI...)

# ------------------------------------------------------------------ the story
TITRE = 'MON TITRE'                 # ONE title everywhere (HUD, YouTube, Shorts); only « PARTIE N » changes on the Shorts
TITRE_HUD = None                    # optional: the title on screen in two lines, e.g. ['LA VOISINE', 'DU 4']
STYLE = 'ps1'                       # 'ps1' (PIXEL 3D, CPU) or 'voxel' (GPU painter): same staging, other drawing
FORMATS = ('16:9', '9:16')          # the long film AND the vertical Shorts (each format has its own framings: F.v)
PARTIE_MAX = 0                      # no internal cap and no automatic split, even when script.txt has cut marks
FIN_MARGE = 1.4                     # seconds of image after the last phrase of the long film

# places: shot name -> place type (python -m hstudio.histoire catalogue --lieux ; repères : --lieu NOM)
LIEUX = {'couloir': {'type': 'corridor'}}
# characters: id -> look (catalogue --personnages ; docs/FORMAT_EPISODE.md « Personnages »). Never the default hero look by accident.
CAST = {'moi': {'hood': [62, 70, 92], 'jeans': [40, 42, 52], 'hair': [52, 36, 26], 'headphones': False, 'backpack': False}}
# extra episode keys (docs/FORMAT_EPISODE.md), e.g. the grade of Chambre 313
EPISODE = {'grade': {'saturation': .55, 'exposure': 1.08}}
MOTS_CLES = {}                      # {'start of a phrase': 'WORD'} : the word coloured in the subtitle (rarely)
COUPES = []                         # extra Short cut points (phrase numbers or texts), besides « # coupe » in script.txt

# publication texts (LIVRAISON/<TITRE>_publication.pdf); {n} {total} {titre} are replaced for each Short
PUBLICATION = {
    'description_longue': "Une histoire d'horreur originale.\nÀ écouter au casque.",
    'hashtags': ['#horreur', '#histoiredhorreur', '#creepypasta'],
    'tags_long': ["histoire d'horreur", 'horreur', 'creepypasta', 'histoire qui fait peur'],
    'chapitres': [],                # [(0, 'Le début'), ('start of a phrase', 'Chapter name'), ...] : 3 at least, 10 s apart
    'description_short': '{titre} · partie {n}/{total}\n#shorts #horreur #histoiredhorreur #creepypasta',
    'tags_shorts': ["histoire d'horreur", 'horreur', 'shorts horreur'],
    'legende_tiktok': '{titre} ({n}/{total})\n#horreur #histoiredhorreur #creepypasta #pourtoi',
}
MIXAGE = {}                         # rarely: {'corrections_db': {'phone_ring': 2}} after listening


def build(F):
    """called once per format (F.aspect = '16:9' or '9:16'). Write the shots IN ORDER, every phrase in exactly one shot."""
    sh, s, v, frame = F.shot, F.sfx, F.v, F.frame
    n = n_lines()

    # --- sound: a room tone under the whole story (a « bed » needs dur) ---------------------------------------------
    s('amb_room', 0., .35, dur=le(n - 1) + FIN_MARGE)

    # --- REPLACE THIS BLOCK: one shot per phrase, the narrator standing in the corridor, three framings in turn -------
    HERO = (0., 9.)                                                 # (x, z) of the narrator; he faces -z (yaw PI)
    sizes = [('PE', 28, 28), ('PM', 32, 40), ('GP', 45, 65)]        # (shot size of SIZES, f35 in 16:9, f35 in 9:16)
    for i in range(n):
        size, f16, f9 = sizes[i % 3]
        aim = (HERO[0], HEAD_Y if size == 'GP' else CHEST_Y, HERO[1])
        cam = frame(shot_start(i), aim, SIZES[size], v(f16, f9), facing=PI, angle=(12 if i % 2 else -12))
        sh(i, i, [cam], {'moi': [K(0, HERO, PI, face='nervous' if i % 2 else 'neutral')]},
           fx={'fade_in': 1.2} if i == 0 else None)

    # --- RECIPES (copy them into your own shots) ---------------------------------------------------------------------
    # several framings in ONE shot: a CUT key jumps, a plain key glides (camera move)
    #   sh('Tu décroches', 'Une femme murmure', [
    #        C(shot_start('Tu décroches'), [-5.5, 1.36, 4.75], [-4.5, 1.12, 4.75], v(40, 44)),     # insert on the phone
    #        CUT(ls('Une femme murmure'), [-3.8, 1.62, 5.0], head('moi', 1.62), v(56, 58))],       # close-up, follows the head
    #      {'moi': [K(0, (-5.2, 5.5), E_, face='nervous', reach_r=[.12, 1.0, .5, .7]),             # hand reaches the handset
    #               K(ls('Tu décroches') + .55, (-5.2, 5.5), E_, gesture='phone', hold='handset')]},
    #      state={'handset': [1, 0, ls('Tu décroches') + .45, ls('Tu décroches') + .46]})          # the place's state, animated
    #   s('click', ls('Tu décroches') + .45, .7)                                                   # the sound ON the action
    #   s('phone_ring', ls(0) + .2, .55, repeat=3, gap=2.0, stop=ls('Tu décroches') + .45)        # rings until lifted
    #   s('fire_alarm_fr', ls(33) + .45, .55, dur=40., muffle=[ls(60), 1.5])                      # our own fabricated sounds
