"""Installation check (python -m hstudio check): versions, ffmpeg, Python packages, both engines, a tiny MP4."""
import os, sys, shutil, subprocess, tempfile, importlib

def report(log=print):
    ok = True
    def line(good, msg):
        nonlocal ok
        ok &= bool(good); log(('OK      ' if good else 'ERREUR  ') + msg)
    line(sys.version_info >= (3, 10), f'Python {sys.version.split()[0]} (3.10 ou plus)')
    from . import ffmpeg_path
    tools = ffmpeg_path.ensure(); ff = tools['ffmpeg']
    for name in ('ffmpeg', 'ffprobe'):  # ffprobe sert à mesurer les durées : un ffmpeg seul ne suffit pas
        line(tools[name], f'{name} : {tools[name] or "introuvable. " + ffmpeg_path.INSTALL_HINT}')
    for mod in ('numpy', 'PIL', 'fastapi', 'uvicorn', 'requests'):
        try: m = importlib.import_module(mod); line(True, f'{mod} {getattr(m, "__version__", "")}')
        except Exception as e: line(False, f'{mod} manquant ({e}) : pip install -r requirements.txt')
    for mod in ('anthropic', 'google.genai'):
        try: importlib.import_module(mod); log(f'OK      {mod} (réalisateur IA, facultatif)')
        except Exception: log(f'info    {mod} absent : seulement nécessaire pour ce réalisateur IA')
    from . import paths
    from .pipeline import load_settings, make_engine
    s = load_settings()
    log('info    clé ElevenLabs : ' + ('renseignée' if s.get('elevenlabs_api_key') else 'absente (voix de brouillon seulement)'))
    log('info    réalisateur : ' + str(s.get('director')) + (' (clé renseignée)' if s.get('anthropic_api_key') or s.get('gemini_api_key') else ' (sans clé IA : mode automatique)'))
    try:
        lines = [{'tts': 'x', 'display': 'Test', 'text': 'Test', 'tags': [], 'dialogue': False, 'i': 0, 'start': 0.1, 'end': 1.0, 'segs': [[.1, 1.]]}]
        for style, ep in (('pixel3d', {'engine_version': 2, 'default_set': 'park', 'cast': {'lea': {'ref': 'lea'}},
                                        'shots': [{'lines': [0, 0], 'actors': [{'id': 'lea', 'at': [0, 3]}], 'actions': [{'who': 'lea', 'do': 'walk_to', 'to': [0.5, 4]}], 'camera': {'shot': 'full', 'on': ['lea']}}]}),
                          ('console', {'shots': [{'lines': [0, 0], 'scene': {'type': 'door'}}]})):
            for asp in ('9:16', '16:9'):
                im = make_engine(style, ep, lines, None if False else __import__('numpy').zeros(10), 1.2, asp).frame(.5)
                line(im.size == ((1080, 1920) if asp == '9:16' else (1920, 1080)), f'moteur {style} {asp} : image {im.size[0]}x{im.size[1]}')
    except Exception as e:
        line(False, f'moteurs : {e}')
    if ff:
        d = tempfile.mkdtemp(); out = os.path.join(d, 't.mp4')
        r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', out], capture_output=True)
        line(r.returncode == 0 and os.path.exists(out), 'encodage MP4 (libx264)')
        if tools['ffprobe'] and os.path.exists(out):  # relecture : prouve que ffprobe fonctionne, pas seulement qu'il existe
            p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', out], capture_output=True, text=True)
            line(p.stdout.strip() == 'h264', f'relecture MP4 par ffprobe : {p.stdout.strip() or "illisible"}')
        shutil.rmtree(d, ignore_errors=True)
    line(os.access(paths.PROJECTS if os.path.isdir(paths.PROJECTS) else paths.ROOT, os.W_OK), f'dossier des projets inscriptible : {paths.PROJECTS}')
    log('Tout est prêt.' if ok else 'Corrige les lignes ERREUR ci-dessus.')
    return ok
