"""Étape LIVRER du kit : image (rendus/) + son (mix/) -> LIVRAISON/, puis TOUT est mesuré sur les fichiers finaux.

Pour chaque version (film long 16:9, Shorts 9:16) :
  * assemblage sans réencoder l'image (AAC 256k), décodage complet, durée, taille d'image ;
  * sonie intégrée et crête vraie (ebur128) : -14 LUFS ±0,5 et ≤ -1 dBTP exigés ;
  * copie allégée « _leger » (720p, deux passes, < 30 Mo) pour l'envoi dans le chat, mesurée elle aussi ;
  * planche tirée DU FICHIER FINAL (une image par cadrage) -> planches/final_<version>_NN.jpg : À REGARDER ;
puis LIVRAISON/_mesures.json, LIVRAISON/RAPPORT_MESURES.md, LIVRAISON/<TITRE>_publication.pdf (+ publication.txt).
Rien n'est publié ni envoyé.

    python -m hstudio.histoire livrer <dossier> [--sans-leger] [--sans-pdf]"""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from .common import ENGINE, KitError, Story, decode_ok, loudness, probe, read_json, slug, write_json, write_text, other_python, version_hash
from . import projet as PJ
from . import rendu as RD
from . import lib

LIGHT_MB = 28.
LIGHT_LIMIT_MB = 30.
# Owner's permanent rule (9/11/2026): the thumbnail always opens the video for a very short time (it also becomes the TikTok cover frame).
# The story folder's thumbnail (miniatures/, copied by `planifier --produire`) is laid over the first MINIATURE_DEBUT seconds of every
# delivered version of the same shape; `MINIATURE_DEBUT = 0` in histoire.py switches it off. Without a thumbnail nothing changes.
MINIATURE_DEBUT = .4


def thumbnail(st):
    d = os.path.join(st.dir, 'miniatures')
    if not os.path.isdir(d): return None
    fs = sorted(f for f in os.listdir(d) if f.lower().endswith(('.png', '.jpg', '.jpeg')))
    return os.path.join(d, fs[0]) if fs else None


def thumb_fits(thumb, size):
    """the thumbnail has the shape of the video (9:16 on 9:16, 16:9 on 16:9), within 6 %"""
    with Image.open(thumb) as im: a = im.width / im.height
    return abs(a / (size[0] / size[1]) - 1) <= .06


def mux(video, wav, out, dur, thumb=None, thumb_s=0., size=None):
    tmp = out + '.part.mp4'
    if thumb and thumb_s > 0 and size:
        w, h = size
        fc = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[m];"
              f"[0:v][m]overlay=0:0:enable='lt(t,{thumb_s:.3f})':eof_action=pass[v]")
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-loop', '1', '-t', f'{thumb_s + .5:.3f}', '-i', thumb, '-i', wav, '-filter_complex', fc,
                        '-map', '[v]', '-map', '2:a', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                        '-t', f'{dur:.3f}', '-movflags', '+faststart', tmp], check=True)
    else:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
                        '-t', f'{dur:.3f}', '-movflags', '+faststart', tmp], check=True)
    os.replace(tmp, out)


def thumb_shown(path, thumb, size, t=.15):
    """measured on the delivered file: the frame at t looks like the thumbnail (mean absolute difference, 0..255)"""
    w, h = (108, 192) if size[1] > size[0] else (192, 108)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    if len(raw) < w * h * 3: return 255.
    a = np.frombuffer(raw[:w * h * 3], np.uint8).reshape(h, w, 3).astype(np.float32)
    with Image.open(thumb) as im: b = np.asarray(im.convert('RGB').resize((w, h), Image.BILINEAR), np.float32)
    return float(np.abs(a - b).mean())


def light(src, dst, dur, vertical, wav):
    """720p two-pass video; the sound from the master WAV (re-encoding the 256k AAC at 128k overshoots the true peak), through
    loudnorm with a lower true-peak ceiling so that the 128k AAC still lands at or under -1 dBTP"""
    kbps = max(250, min(4500, int(LIGHT_MB * 8 * 1024 / dur) - 128 - 20))
    sc = 'scale=720:1280:flags=lanczos' if vertical else 'scale=1280:720:flags=lanczos'
    tmp = tempfile.mkdtemp(prefix='kit_leger_'); log = os.path.join(tmp, 'p')
    base = ['ffmpeg', '-y', '-v', 'error', '-i', src, '-i', wav, '-map', '0:v', '-map', '1:a', '-vf', sc, '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k',
            '-pix_fmt', 'yuv420p', '-passlogfile', log]
    try:
        subprocess.run(base + ['-pass', '1', '-an', '-f', 'mp4', os.devnull], check=True, cwd=tmp)
        subprocess.run(base + ['-pass', '2', '-af', 'loudnorm=I=-14:TP=-3.0:LRA=11,aresample=44100', '-c:a', 'aac', '-b:a', '128k', '-t', f'{dur:.3f}',
                               '-movflags', '+faststart', dst], check=True, cwd=tmp)
        # 15/11/2026 (Le Phare qui efface, partie 3) : sharp transients (glass, knocks) made the 128k AAC overshoot to -0.7 dBTP despite the
        # -3 ceiling. Only when the MEASURED copy is over -1 dBTP: the sound alone is re-encoded with a lower ceiling (the video stream is copied).
        # A compliant copy is never touched (same bytes as before).
        for ceil in (-4.5, -6.0):
            _, tp, _ = loudness(dst)
            if tp <= -1.0: break
            fix = os.path.join(tmp, 'tp.mp4')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', dst, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                            '-af', f'loudnorm=I=-14:TP={ceil}:LRA=11,aresample=44100', '-c:a', 'aac', '-b:a', '128k', '-t', f'{dur:.3f}',
                            '-movflags', '+faststart', fix], check=True, cwd=tmp)
            shutil.move(fix, dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def final_sheet(st, v, path):
    """frames taken FROM THE DELIVERED FILE, one per camera setup -> jpg paths"""
    from .apercu import _font
    items = RD.sample_times(st.version_dir(v['id'])); vertical = v['aspect'] == '9:16'
    w, h = (270, 480) if vertical else (480, 270); cols = 8 if vertical else 6; per = 48 if vertical else 36
    f = _font(10); out = []
    os.makedirs(st.planches, exist_ok=True)
    for n0 in range(0, len(items), per):
        chunk = items[n0:n0 + per]; rows = (len(chunk) + cols - 1) // cols
        im = Image.new('RGB', (cols * w, rows * (h + 16)), (10, 10, 12)); d = ImageDraw.Draw(im)
        for i, (k, ln, t) in enumerate(chunk):
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-vf', f'scale={w}:{h}', '-f', 'rawvideo',
                                  '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
            fr = Image.frombytes('RGB', (w, h), raw[:w * h * 3]) if len(raw) >= w * h * 3 else Image.new('RGB', (w, h), (255, 0, 255))
            x, y = (i % cols) * w, (i // cols) * (h + 16); im.paste(fr, (x, y + 16))
            d.text((x + 3, y + 3), f"P{k} L{ln[0] + v['lines'][0]}-{ln[1] + v['lines'][0]} {t:.1f}s", font=f, fill=(236, 230, 210))
        p = os.path.join(st.planches, f"final_{v['id']}_{n0 // per:02d}.jpg"); im.save(p, quality=86); out.append(p)
    return out, len(items), len({k for k, _, _ in items})


# ------------------------------------------------------------------ publication texts
def _ts(sec):
    s = max(0, int(sec)); return f'{s // 60:02d}:{s % 60:02d}' if s < 3600 else f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}'


def publication(st, mod, dec, files, log=print):
    P = dict(getattr(mod, 'PUBLICATION', {}) or {}); title = str(mod.TITRE); warns = []
    lines = read_json(st.lignes); lib.use_lines(lines)
    if not P: warns.append('PUBLICATION absent de histoire.py : textes minimaux (titres seulement) — écris-le (voir le modèle)')
    hashtags = P.get('hashtags') or ['#horreur', '#histoiredhorreur', '#creepypasta']
    if isinstance(hashtags, str): hashtags = hashtags.split()
    chap = []
    for i, (where, name) in enumerate(P.get('chapitres') or []):
        t = 0. if i == 0 else lib.shot_start(where)
        chap.append((t, name))
    if chap:
        if len(chap) < 3: warns.append('YouTube exige au moins 3 chapitres : chapitres ignorés'); chap = []
        elif any(b[0] - a[0] < 10 for a, b in zip(chap, chap[1:])): warns.append('deux chapitres à moins de 10 s : YouTube les refuse, espace-les')
    desc_long = (P.get('description_longue') or f'{title}. Une histoire d\'horreur originale.').strip()
    if chap: desc_long += '\n\nChapitres\n' + '\n'.join(f'{_ts(t)} {n}' for t, n in chap)
    desc_long += '\n\n' + ' '.join(hashtags[:3])
    tags_long = ', '.join(P.get('tags_long') or ["histoire d'horreur", 'horreur', 'creepypasta', title.lower()])
    if len(tags_long) > 500: warns.append(f'tags du film long : {len(tags_long)} caractères (> 500, YouTube coupe)')
    parts = [v for v in dec['versions'] if v['id'].startswith('partie')]; tot = len(parts)
    shorts = []
    for k, v in enumerate(parts, 1):
        fmt = dict(n=k, total=tot, titre=title, partie=(f'PARTIE {k}' if tot > 1 else ''))
        ds = P.get('description_short') or ('{titre}' + (' · partie {n}/{total}' if tot > 1 else '') + '\n#shorts #horreur #histoiredhorreur')
        ds = ds[k - 1] if isinstance(ds, (list, tuple)) else ds
        tt = P.get('legende_tiktok') or ('{titre}' + (' ({n}/{total})' if tot > 1 else '') + '\n#horreur #histoiredhorreur #creepypasta #pourtoi')
        tt = tt[k - 1] if isinstance(tt, (list, tuple)) else tt
        f = next((x for x in files if x['version'] == v['id']), {})
        shorts.append(dict(nom=(f'Partie {k}' if tot > 1 else 'Short'), fichier=f.get('fichier', ''), titre=f'{title} · PARTIE {k}' if tot > 1 else title,
                           description=ds.format(**fmt), tiktok=tt.format(**fmt)))
    tags_shorts = ', '.join(P.get('tags_shorts') or [])
    cut_txt = ''
    if tot > 1:
        cut_txt = ' '.join(f"La partie {k} ({v['dur'] // 60:.0f} min {v['dur'] % 60:02.0f} s) commence sur « {lines[v['lines'][0]]['text'][:70]} »"
                           f"{' et finit sur « ' + lines[v['lines'][1]]['text'][:70] + ' »' if k < tot else ''}." for k, v in enumerate(parts, 1))
    data = dict(titre=title, sous_titre=f"Dossier de publication · {datetime.date.today().strftime('%d/%m/%Y')} · style {dec['style'].upper()}",
                fichiers=[f for f in files], long=None, shorts=shorts, tags_shorts=tags_shorts, decoupe_texte=cut_txt, images=[], avertissements=warns)
    if any(v['id'] == 'long_16x9' for v in dec['versions']):
        data['long'] = dict(titre=title, description=desc_long, hashtags=' '.join(hashtags[:3]), tags=tags_long, chapitres=bool(chap))
    # plain text copy (always written, even without reportlab)
    txt = [f'{title} — textes de publication (rien n\'est publié)', '']
    if data['long']: txt += ['== YouTube, version longue ==', 'Titre : ' + title, '', 'Description :', desc_long, '', 'Tags : ' + tags_long, '']
    for sh in shorts: txt += [f"== {sh['nom']} ({sh['fichier']}) ==", 'Titre Shorts : ' + sh['titre'], 'Description Shorts :', sh['description'], 'Légende TikTok :', sh['tiktok'], '']
    if tags_shorts: txt += ['Tags Shorts : ' + tags_shorts, '']
    if warns: txt += ['ATTENTION :'] + ['- ' + w for w in warns]
    write_text(os.path.join(st.livraison, 'publication.txt'), '\n'.join(txt) + '\n')
    return data, warns


def make_pdf(st, data, title, log=print):
    out = os.path.join(st.livraison, f'{slug(title)}_publication.pdf')
    dpath = os.path.join(st.livraison, '_publication_donnees.json'); write_json(dpath, data)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdf_publication.py')
    py = other_python(['reportlab'], 'HSTUDIO_PYTHON_PDF')
    if not py:
        log('! aucun Python avec reportlab : PDF non fait (les textes sont dans LIVRAISON/publication.txt). Variable HSTUDIO_PYTHON_PDF.')
        return None
    r = subprocess.run(py + [script, dpath, out], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0: log('! PDF échoué : ' + (r.stderr or '')[-600:]); return None
    return out


def deliver(folder, light_copies=True, pdf=True, log=print):
    st = Story(folder)
    dec, mod = PJ.build(folder, log, quiet=True)
    title = str(mod.TITRE); name = slug(title)
    os.makedirs(st.livraison, exist_ok=True)
    allm = {}; files = []; fails = []
    for v in PJ.versions(st):
        video = st.need(st.video_only(v['id']), f"fais l'étape rendre ({v['id']})")
        wav = st.need(st.mix_wav(v['id']), "fais l'étape mixer")
        stamp = video.replace('.mp4', '.json')
        if not os.path.exists(stamp) or read_json(stamp).get('episode_sha1') != version_hash(st.version_dir(v['id'])):
            raise KitError(f"{v['id']} : l'image a été rendue avec une AUTRE mise en scène que l'actuelle (histoire.py a changé) : relance rendre")
        if read_json(stamp).get('secondes'):
            raise KitError(f"{v['id']} : le rendu est partiel (--secondes) : relance rendre sans --secondes")
        out = os.path.join(st.livraison, f"{name}_{v['id']}.mp4")
        size = (1920, 1080) if v['aspect'] == '16:9' else (1080, 1920)
        th = thumbnail(st); th_s = float(getattr(mod, 'MINIATURE_DEBUT', MINIATURE_DEBUT) or 0.)
        if not (th and th_s > 0 and thumb_fits(th, size)): th_s = 0.
        log(f"livraison {v['id']}…" + (f" (miniature au début : {th_s:.2f} s)" if th_s else '')); mux(video, wav, out, v['dur'], th, th_s, size)
        ok, err = decode_ok(out); info = probe(out); I, tp, _ = loudness(out)
        want = '1920x1080' if v['aspect'] == '16:9' else '1080x1920'
        checks = {'décodage complet': ok, f'image {want}': info.get('image') == want, f"durée {v['dur']:.2f} s (±0,1)": abs(info['duree'] - v['dur']) <= .1,
                  '-14 LUFS ±0,5': abs(I + 14.) <= .5, 'crête ≤ -1 dBTP': tp <= -1.0}
        if th_s:
            diff = thumb_shown(out, th, size, min(.15, th_s / 2)); checks['miniature au début (mesurée sur le fichier)'] = diff < 22.
        if v['id'].startswith('partie') and dec.get('partie_max', 0) > 0:
            checks['durée demandée respectée'] = v['dur'] <= dec['partie_max'] + .01
        m = dict(fichier=os.path.basename(out), version=v['id'], decodage_complet=ok, erreurs=err, **info, LUFS=round(I, 2), crete_dBTP=round(tp, 2))
        if th_s: m['miniature_debut'] = dict(fichier=th, secondes=round(th_s, 3), ecart_image=round(diff, 1))
        if light_copies:
            lp = out.replace('.mp4', '_leger.mp4'); light(out, lp, info['duree'], v['aspect'] == '9:16', wav)
            lok, _ = decode_ok(lp); li = probe(lp); lI, ltp, _ = loudness(lp)
            m['leger'] = dict(fichier=os.path.basename(lp), decodage_complet=lok, LUFS=round(lI, 2), crete_dBTP=round(ltp, 2), **li)
            checks['copie légère < 30 Mo'] = li['taille_mo'] < LIGHT_LIMIT_MB; checks['copie légère décodée'] = lok
            checks['copie légère -14 LUFS ±1, ≤ -1 dBTP'] = abs(lI + 14.) <= 1. and ltp <= -1.0
        sheets, n_setups, n_shots = final_sheet(st, v, out)
        m.update(plans=n_shots, cadrages=n_setups, planches=sheets, controles=checks)
        allm[v['id']] = m; files.append(dict(m, version=v['id']))
        if light_copies: files.append(dict(m['leger'], version=v['id'] + '_leger'))
        bad = [k for k, ok_ in checks.items() if not ok_]
        log(f"  {m['fichier']} : {info['duree']:.2f} s, {info.get('image')}, {info['taille_mo']} Mo, {I:.1f} LUFS, {tp:.1f} dBTP"
            + (f" ; léger {m['leger']['taille_mo']} Mo, {m['leger']['LUFS']:.1f} LUFS, {m['leger']['crete_dBTP']:.1f} dBTP" if light_copies else '')
            + (' ✓' if not bad else ' ✗ ' + ', '.join(bad)))
        fails += [f"{v['id']} : {b}" for b in bad]
    write_json(os.path.join(st.livraison, '_mesures.json'), allm)
    data, warns = publication(st, mod, dec, [f for f in files if not f['version'].endswith('_leger')], log)
    data['fichiers'] = files
    for vid, m in allm.items():
        if vid in ('long_16x9', 'partie1_9x16') and m.get('planches'):
            p = os.path.join(st.livraison, f'_couverture_{vid}.jpg'); vv = next(v for v in dec['versions'] if v['id'] == vid)
            t = min(vv['dur'] * .3, 20.); subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', os.path.join(st.livraison, m['fichier']), '-frames:v', '1', '-q:v', '3', p])
            if os.path.exists(p): data['images'].append(dict(path=p, w=16 if vid.startswith('long') else 9, h=9 if vid.startswith('long') else 16))
    pdf_path = make_pdf(st, data, title, log) if pdf else None
    for w in warns: log('! ' + w)
    rep = [f'# {title} — rapport de mesures de la livraison', '', f"Mesuré le {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} sur les fichiers de LIVRAISON/. Rien n'a été publié.", '',
           '| Fichier | Image | Durée | Taille | Sonie | Crête | Contrôles |', '|---|---|---|---|---|---|---|']
    for vid, m in allm.items():
        bad = [k for k, ok_ in m['controles'].items() if not ok_]
        rep.append(f"| {m['fichier']} | {m.get('image')} | {m['duree']:.2f} s | {m['taille_mo']} Mo | {m['LUFS']:.1f} LUFS | {m['crete_dBTP']:.1f} dBTP | {'✓ tout' if not bad else '✗ ' + ', '.join(bad)} |")
        if 'leger' in m:
            l_ = m['leger']; rep.append(f"| {l_['fichier']} | {l_.get('image')} | {l_['duree']:.2f} s | {l_['taille_mo']} Mo | {l_['LUFS']:.1f} LUFS | {l_['crete_dBTP']:.1f} dBTP | copie d'envoi |")
    rep += ['', '## Planches tirées des fichiers finaux (à regarder avant de dire que c\'est fini)', '']
    for vid, m in allm.items(): rep += [f'- {p}' for p in m['planches']]
    rep += ['', f"PDF de publication : {pdf_path or 'non fait (voir publication.txt)'}", f"Textes : {os.path.join(st.livraison, 'publication.txt')}"]
    if warns: rep += ['', '## Avertissements', ''] + [f'- {w}' for w in warns]
    if fails: rep += ['', '## ÉCHECS', ''] + [f'- {f}' for f in fails]
    write_text(os.path.join(st.livraison, 'RAPPORT_MESURES.md'), '\n'.join(rep) + '\n')
    log(f"→ {os.path.join(st.livraison, 'RAPPORT_MESURES.md')}" + (f'\n→ {pdf_path}' if pdf_path else ''))
    log('REGARDE les planches finales (liste dans le rapport) avant de livrer au propriétaire. Rien n\'est publié.')
    if fails: raise KitError('livraison NON conforme : ' + ' ; '.join(fails))
    return allm
