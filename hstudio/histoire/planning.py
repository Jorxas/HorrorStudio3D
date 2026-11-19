"""Étape PLANIFIER du kit : les vidéos prévues à l'avance (script + miniature + date), avant que leur dossier de production n'existe.

Un dossier par vidéo prévue, dans PLANNING (Desktop\\videpgene\\PLANNING, ou $HSTUDIO_PLANNING_DIR) :

    PLANNING\\2026-11-07_MON_TITRE\\
        fiche.json          titre, date prévue, statut, notes
        script.txt          le texte, au format du kit (balises, « # rythme », « # coupe »)
        miniature.png       déposée par le propriétaire (.png, .jpg ou .jpeg) ; aucun service payant

    python -m hstudio.histoire planifier                              liste, par date, avec ce qui manque
    python -m hstudio.histoire planifier --ajouter "Titre" --date 2026-11-07
    python -m hstudio.histoire planifier --produire [NOM]             crée HISTOIRE_<NOM> avec ce script et cette miniature
                                                                      (sans NOM : la prochaine prévue, « ► » de la liste ; refus expliqué si elle est incomplète)
    python -m hstudio.histoire planifier --terminer NOM               marque la vidéo comme faite

Règles tenues ici :
  * rien n'est dépensé ni publié par cette étape ; --produire écrit seulement le dossier de production et son
    AUTORISATION_PRODUCTION.json (publication_authorized: false) ;
  * une vidéo prévue vaut accord permanent du propriétaire pour sa voix ElevenLabs (décision du 04/11/2026 : aucun plafond) ;
    le nombre de caractères est tout de même annoncé, et la voix n'est jamais régénérée sans --refaire ;
  * une vidéo n'est « prête » que si son script a des phrases et si sa miniature est présente et lisible."""
import datetime
import hashlib
import os
import shutil

from . import script as SC
from .common import KitError, Story, read_json, write_json, slug

STATUTS = ('prevue', 'en_production', 'terminee')
THUMB_EXT = ('.png', '.jpg', '.jpeg')
THUMB_MAX_MO = 2.0                       # YouTube refuses a custom thumbnail above 2 MB


def root():
    return os.environ.get('HSTUDIO_PLANNING_DIR') or os.path.join(os.path.expanduser('~'), 'Desktop', 'videpgene', 'PLANNING')


def _today():
    return datetime.date.today()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def _parse_date(s):
    try: return datetime.date.fromisoformat(str(s))
    except ValueError: raise KitError(f"date « {s} » : écris AAAA-MM-JJ, par exemple 2026-11-07") from None


def _thumb(folder):
    for ext in THUMB_EXT:
        p = os.path.join(folder, 'miniature' + ext)
        if os.path.exists(p): return p
    return None


def _thumb_info(path):
    """-> (largeur, hauteur, Mo) ; raises KitError when the file is not an image Pillow can open"""
    try:
        from PIL import Image
        with Image.open(path) as im: w, h = im.size
    except Exception as e:
        raise KitError(f'miniature illisible ({os.path.basename(path)}) : {type(e).__name__}') from None
    return w, h, os.path.getsize(path) / 1048576


class Entry:
    """one planned video: its fiche, and what is still missing before it can be produced"""

    def __init__(self, folder):
        self.dir = folder; self.name = os.path.basename(folder)
        self.fiche_path = os.path.join(folder, 'fiche.json'); self.fiche = read_json(self.fiche_path)
        self.script = os.path.join(folder, 'script.txt')
        self.titre = str(self.fiche.get('titre') or self.name)
        self.statut = self.fiche.get('statut', 'prevue')
        try: self.date = _parse_date(self.fiche.get('date'))
        except KitError: self.date = None
        self.chars = None; self.phrases = None; self.thumb = _thumb(folder); self.thumb_dims = None
        self.missing = []; self.warnings = []
        self._inspect()

    def _inspect(self):
        if self.date is None: self.missing.append('date invalide dans fiche.json')
        if self.statut not in STATUTS: self.missing.append(f'statut inconnu « {self.statut} » ({", ".join(STATUTS)})')
        if not os.path.exists(self.script): self.missing.append('script.txt absent')
        else:
            try:
                sc = SC.parse(self.script)
                self.chars = sum(p['chars'] for p in sc['parts']); self.phrases = len(sc['phrases'])
                self.warnings += sc['warnings']
            except KitError as e:
                self.missing.append('script vide' if 'aucune phrase' in str(e) else str(e).splitlines()[0])
        if self.thumb is None: self.missing.append('miniature absente (dépose miniature.png ou miniature.jpg)')
        else:
            try:
                w, h, mo = _thumb_info(self.thumb); self.thumb_dims = (w, h, mo)
                if mo > THUMB_MAX_MO: self.warnings.append(f'miniature de {mo:.1f} Mo : YouTube refuse plus de {THUMB_MAX_MO:.0f} Mo')
            except KitError as e: self.missing.append(str(e))

    @property
    def ready(self): return self.statut == 'prevue' and not self.missing


def load_all():
    base = root()
    if not os.path.isdir(base): return []
    out = []
    for n in sorted(os.listdir(base)):
        d = os.path.join(base, n)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'fiche.json')):
            try: out.append(Entry(d))
            except (OSError, ValueError) as e: raise KitError(f'{os.path.join(d, "fiche.json")} illisible : {e}') from None
    return sorted(out, key=lambda e: (e.date or datetime.date.max, e.name))


def _find(entries, name):
    """the entry named by `name` (folder name, slug or part of the title); without a name, the earliest planned one"""
    pending = [e for e in entries if e.statut == 'prevue']
    if not name:
        if not pending: raise KitError('aucune vidéo prévue dans ' + root())
        return pending[0]
    key = slug(name); hits = [e for e in entries if name == e.name or key in slug(e.name) or key in slug(e.titre)]
    exact = [e for e in hits if name == e.name]
    hits = exact or hits
    if not hits: raise KitError(f'aucune vidéo prévue ne correspond à « {name} » (planifier, sans option, les liste)')
    if len(hits) > 1: raise KitError('plusieurs vidéos correspondent à « ' + name + ' » : ' + ', '.join(e.name for e in hits))
    return hits[0]


# ------------------------------------------------------------------ commands
def lister(log):
    entries = load_all(); today = _today()
    log(f'PLANNING — {root()}   (aujourd\'hui {today.isoformat()})')
    if not entries:
        log('  (aucune vidéo prévue)\n  Pour en prévoir une : python -m hstudio.histoire planifier --ajouter "Titre" --date AAAA-MM-JJ'); return entries
    first = next((e for e in entries if e.statut == 'prevue'), None)
    for e in entries:
        mark = '►' if e is first else ' '
        d = e.date.isoformat() if e.date else '????-??-??'
        late = ' (EN RETARD)' if e.date and e.statut == 'prevue' and e.date < today else ''
        etat = {'prevue': 'prête' if e.ready else 'incomplète', 'en_production': 'en production', 'terminee': 'terminée'}.get(e.statut, e.statut)
        log(f' {mark} {d}  {e.titre}  — {etat}{late}')
        if e.statut == 'prevue' or e.missing:
            bits = []
            if e.chars is not None: bits.append(f'script {e.chars} caractères, {e.phrases} phrases')
            if e.thumb_dims: bits.append(f'miniature {e.thumb_dims[0]}x{e.thumb_dims[1]}')
            log('      ' + ' · '.join(bits))
        for m in e.missing: log('      ✗ ' + m)
        for w in e.warnings: log('      ! ' + w)
    log('► = la prochaine à produire. « Fais la vidéo » prend la première prête : planifier --produire')
    return entries


def ajouter(titre, date, log):
    d = _parse_date(date)
    folder = os.path.join(root(), f'{d.isoformat()}_{slug(titre)}')
    if os.path.exists(folder): raise KitError(f'existe déjà : {folder}')
    os.makedirs(folder)
    write_json(os.path.join(folder, 'fiche.json'), dict(titre=titre, date=d.isoformat(), statut='prevue', style='ps1', format='9:16', notes=''))
    with open(os.path.join(folder, 'script.txt'), 'w', encoding='utf-8') as f:
        f.write(f'# Script de « {titre} » (prévu le {d.isoformat()}). Écris le texte sous ces lignes, une phrase par ligne.\n'
                '# Balises ElevenLabs sobres ; « # rythme NOM VITESSE » pour changer la vitesse ; « # coupe » avant une phrase de suspense.\n')
    log(f'prévue : {folder}\n  → écris script.txt, dépose miniature.png (ou .jpg) dans ce dossier, puis : planifier')


def produire(name, log):
    e = _find(load_all(), name)                       # without a name: the earliest planned one, the « ► » of the list
    if e.statut != 'prevue': raise KitError(f'« {e.titre} » est déjà {e.statut.replace("_", " ")} ({e.fiche.get("histoire", "")})')
    if e.missing: raise KitError(f'« {e.titre} » n\'est pas prête :\n' + '\n'.join('  ✗ ' + m for m in e.missing))
    from . import cli
    from .voix import settings
    story_dir = os.path.join(os.path.dirname(root()), 'HISTOIRE_' + slug(e.titre))
    if os.path.exists(story_dir): raise KitError(f'le dossier de production existe déjà : {story_dir} (rien n\'est écrasé)')
    st = Story(story_dir)
    os.makedirs(st.dir)
    shutil.copy2(e.script, st.script)                                   # `nouveau` keeps an existing script.txt
    cli.nouveau(st.dir, e.titre)
    mdir = os.path.join(st.dir, 'miniatures'); os.makedirs(mdir)
    ext = os.path.splitext(e.thumb)[1].lower(); thumb_dst = os.path.join(mdir, slug(e.titre) + ext)
    shutil.copy2(e.thumb, thumb_dst)
    v = settings(st); sha_script = _sha256(st.script)
    write_json(os.path.join(st.dir, 'AUTORISATION_PRODUCTION.json'), dict(
        date=_today().isoformat(), request=f'Vidéo programmée à l\'avance (PLANNING\\{e.name}), demandée par le propriétaire',
        voice_characters=e.chars, voice=v['voice_id'], model=v['modele'], paid_transcription=False,
        production_authorized=True, publication_authorized=False,
        voix_autorisee_par_planning=True,
        sources=[dict(file=st.script, sha256=sha_script)], miniature_sha256=_sha256(thumb_dst),
        planning=dict(fiche=e.fiche_path, date_prevue=e.date.isoformat())), indent=2)
    e.fiche.update(statut='en_production', histoire=st.dir, produite_le=_today().isoformat())
    write_json(e.fiche_path, e.fiche, indent=2)
    log(f'\nProduction ouverte pour « {e.titre} » : {st.dir}')
    log(f'  script : {e.chars} caractères, {e.phrases} phrases ; miniature copiée : {thumb_dst}')
    log(f'  voix : autorisée par la programmation (sans plafond) → `voix --oui` sans redemander ; {e.chars} caractères à envoyer, à annoncer au propriétaire')
    log('  publication : non autorisée (publication_authorized: false). Étape suivante : voix, puis phrases, mise en scène (histoire.py), etc.')
    return st.dir


def terminer(name, log):
    if not name: raise KitError('indique quelle vidéo : planifier --terminer NOM')
    e = _find(load_all(), name)
    e.fiche['statut'] = 'terminee'; e.fiche['terminee_le'] = _today().isoformat()
    write_json(e.fiche_path, e.fiche, indent=2)
    log(f'terminée : {e.titre}')


def run(a, log):
    """entry point of the CLI stage (a = argparse namespace of cli.main)"""
    if a.ajouter: ajouter(a.ajouter, a.date or '', log)
    elif a.produire: produire(a.dossier, log)
    elif a.terminer: terminer(a.dossier, log)
    else: lister(log)
