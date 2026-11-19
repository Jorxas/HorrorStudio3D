"""python tools/fusion_page.py [out_dir]  -> local HTML page (no server, no network): « La marche » A | B | unifié side by side, synchronised,
plus the original clip, with the measured figures of every file and the annotations.

The three videos are COPIED next to the page (originals untouched) so the folder can be moved or sent as is."""
import hashlib, html, json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu.films import la_marche as LM

FU = ROOT / 'projects' / 'fusion_20261029'
SRC = {
    'A': Path(r'C:\Users\demo\Videos\moteur_voxel\La_marche_720p_v2.mp4'),
    'B': Path(r'C:\Users\demo\.claude-code-bridge\worktrees\horror-studio-v2\studio-integration\projects\la_marche_20261028\la_marche_720x1280_24fps.mp4'),
    'U': FU / 'livraison' / 'la_marche_unifie_720x1280_24fps_leger.mp4',
}
CLIPS = sorted((FU / 'livraison').glob('dix_mondes_dix_genres_*_leger.mp4'))
LOAD = {'A': 'A — moteur voxel V4.1 (film_marche.js, GPU, `La_marche_720p_v2.mp4`)', 'B': 'B — Horror Studio V3 (NumPy CPU, `la_marche_720x1280_24fps.mp4`)', 'U': 'Unifié — B dirige, A peint (RTX 4060)'}


def probe(p):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(p)], capture_output=True, text=True).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video'); a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    eb = subprocess.run(['ffmpeg', '-nostats', '-i', str(p), '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    import re
    lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', eb)
    return dict(size_mb=round(int(j['format']['size']) / 1e6, 1), dur=float(j['format']['duration']), res=f"{v['width']}×{v['height']}", fps=v['r_frame_rate'].split('/')[0],
                frames=v.get('nb_frames', '?'), codec=f"{v['codec_name']} {v.get('profile', '')}", vbr=round(int(v.get('bit_rate', 0)) / 1e6, 1),
                audio=(f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']} ch" if a else 'aucun'), lufs=(lufs[-1] if lufs else '—'),
                sha=hashlib.sha256(Path(p).read_bytes()).hexdigest())


NOTES = [
    ('Ville au matin', 'Même ville, même soleil, mêmes arbres et voitures dans A et dans l\'unifié : c\'est le peintre de A. B dessine ses propres façades (enseignes « PIZZA ») en raster agrandi.'),
    ('Parc', 'Lina marche à côté de Noé, un passant est assis sur le banc : ici dirigés par la régie de B (trajets parallèles à 0,95 m/s, regards croisés).'),
    ('Automne', 'Lina s\'arrête et salue : verbe `walk_to` puis `gesture wave` de B ; l\'expression passe de « soulagée » à « triste ».'),
    ('Ville sous la pluie', 'Reflets mouillés et pluie de A conservés ; les trois passants au parapluie sont ceux de A (accessoire) mais leur bras est un geste B, pas la pose d\'origine.'),
    ('Glacier', 'Empreintes bleutées à chaque talon posé (événements de pas de la régie). Glace et scintillement de A.'),
    ('Ruines en feu', 'Braises, halo et rim orange de A ; le coureur terrorisé est un `run_to` de B.'),
    ('Champ de bataille', 'Duels re-mis en scène avec le geste `knock` de B (A les animait par formule) : moins de combattants lisibles qu\'en A.'),
    ('Invasion', 'Soucoupes et faisceau de A (statiques dans les deux) ; extraterrestres marchant avec Noé, l\'un pointe du doigt.'),
    ('Vaisseau', 'Même hublot, même couloir ; un figurant traverse en sens inverse.'),
    ('La Lune', 'Poussière et empreintes sombres ; flash blanc final identique (59 s) dans A et l\'unifié.'),
]


def main():
    transport = '--transport' in sys.argv       # lighter copy for the mailbox (size limit): A and B recompressed, clips left out
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = Path(args[0]) if args else FU / ('comparaison_transport' if transport else 'comparaison'); out.mkdir(parents=True, exist_ok=True)
    files = {}
    for k, p in SRC.items():
        d = out / {'A': 'A_original_La_marche_720p_v2.mp4', 'B': 'B_original_la_marche_720x1280_24fps.mp4', 'U': 'unifie_la_marche_720x1280_24fps.mp4'}[k]
        if not d.exists():
            if transport and k != 'U': subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(p), '-c:v', 'libx264', '-preset', 'slow', '-crf', '25', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(d)], check=True)
            else: shutil.copyfile(p, d)
        files[k] = d
    clips = []
    for c in ([] if transport else CLIPS):
        d = out / c.name
        if not d.exists(): shutil.copyfile(c, d)
        clips.append(d)
    # always the figures of the ORIGINAL files, even when the page carries lighter copies
    pr = {k: probe(SRC[k]) for k in files}; cp = [probe(p) for p in clips]
    rt = json.loads((FU / 'marche' / 'la_marche_unifie_720x1280_24fps.render.json').read_text(encoding='utf-8'))
    times = {'A': '≈ 70 s (journal d\'A, GPU intégré Intel)', 'B': '1 975,7 s (CPU, 18 processus)', 'U': f"{rt['render_s']:.0f} s (RTX 4060)"}
    esc = html.escape
    chips = ''.join(f'<button onclick="seek({LM.T0[i]})">{i + 1}. {esc(LM.WORLDS[i])} <small>{LM.T0[i]} s</small></button>' for i in range(10))
    vids = ''.join(f'<figure><figcaption>{esc(LOAD[k])}</figcaption><video id="v{k}" src="{files[k].name}" playsinline preload="auto" {"muted" if k != "U" else ""} controls></video></figure>' for k in 'ABU')
    rows = ''.join(f"<tr><th>{esc(LOAD[k].split(' (')[0])}</th><td>{pr[k]['res']}</td><td>{pr[k]['fps']}</td><td>{pr[k]['dur']:.2f} s</td><td>{pr[k]['frames']}</td><td>{esc(pr[k]['codec'])} {pr[k]['vbr']} Mb/s</td><td>{esc(pr[k]['audio'])}</td><td>{pr[k]['lufs']}</td><td>{pr[k]['size_mb']} Mo</td><td>{esc(times[k])}</td><td><code>{pr[k]['sha'][:16]}…</code></td></tr>" for k in 'ABU')
    notes = ''.join(f'<tr><td><a href="#" onclick="seek({LM.T0[i]});return false">{i + 1}. {esc(n)}</a></td><td>{esc(t)}</td></tr>' for i, (n, t) in enumerate(NOTES))
    clip_html = ''.join(f'<figure><figcaption>{esc(c.name)} — {p["res"]}, {p["dur"]:.1f} s, {p["fps"]} i/s, {esc(p["audio"])}, {p["lufs"]} LUFS, <code>{p["sha"][:16]}…</code></figcaption><video src="{c.name}" controls playsinline preload="metadata"></video></figure>' for c, p in zip(clips, cp))
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Moteur unifié — « La marche » A | B | unifié</title><style>
body{{font:15px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:#14161a;color:#e8e8ec}}main{{max-width:1500px;margin:auto;padding:24px}}h1{{font-size:26px}}h2{{margin-top:36px;border-bottom:1px solid #333;padding-bottom:6px}}
.row{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}figure{{margin:0}}figcaption{{font-size:13px;color:#b8bcc8;margin-bottom:6px}}video{{width:100%;background:#000;border-radius:6px}}
.ctl{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}button{{background:#262b35;color:#e8e8ec;border:1px solid #3a4150;border-radius:6px;padding:6px 10px;cursor:pointer}}button:hover{{background:#323a48}}small{{color:#8a93a6}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #333;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#1c2028}}code{{color:#9fd0ff}}.warn{{background:#2a2418;border:1px solid #5a4a20;padding:10px 14px;border-radius:6px}}
input[type=range]{{flex:1;min-width:240px}}.clip{{max-width:{'1000' if clips and '16x9' in clips[0].name else '420'}px}}</style></head><body><main>
<h1>Moteur unifié « B dirige, A peint » — « La marche »</h1>
<p>Trois versions du même film de 61 s (vertical, sans voix) : <b>A</b> = le film écrit à la main dans le moteur voxel ; <b>B</b> = Horror Studio V3 en raster CPU ; <b>unifié</b> = la régie et la caméra de B,
les personnages, les mondes, la lumière et le post-traitement de A, rendus sur la carte NVIDIA. Lecture synchronisée ci-dessous (le son n'est joué que pour l'unifié ; A et B ont chacun leur propre partition).</p>
<div class="row">{vids}</div>
<div class="ctl"><button onclick="playAll()">▶ Lecture synchronisée</button><button onclick="pauseAll()">⏸ Pause</button><input id="sl" type="range" min="0" max="61" step="0.04" value="0" oninput="seek(this.value)"><span id="tc">0.00 s</span></div>
<div class="ctl">{chips}</div>
<h2>Mesures (faites sur les fichiers)</h2>
<table><tr><th></th><th>Résolution</th><th>i/s</th><th>Durée</th><th>Images</th><th>Vidéo</th><th>Audio</th><th>LUFS</th><th>Taille</th><th>Temps de rendu</th><th>SHA-256</th></tr>{rows}</table>
<p><small>Le temps de rendu d'A vient de son journal (20,9 i/s annoncés, GPU Intel) et n'a pas été remesuré ici. Les rendus de B et de l'unifié sont mesurés.</small></p>
<h2>Annotations monde par monde</h2><table>{notes}</table>
<h2>Ce que la comparaison montre — et ce qu'elle ne montre pas</h2>
<ul><li><b>Fidélité à A</b> : position de Noé (0,95 m/s), caméra du brief et dix mondes sont ceux de <code>film_marche.js</code> ; le test <code>tools/check_voxelgpu.py</code> mesure l'écart à 0,00 cm sur les 30 instants vérifiés.</li>
<li><b>Gain sur B</b> : même mise en scène pilotée par script, rendue en vraie 720×1280 sur GPU en 159 s au lieu de 1 976 s (≈ 12×), avec visages, mains, ombres, flou de profondeur, reflets et halo d'A.</li>
<li><b>Gain sur A</b> : le film n'est plus du JavaScript écrit plan par plan, c'est un épisode JSON (trajets A*, caméra par intention, expressions, sous-titres, 16:9 et 9:16, contrôle qualité).</li></ul>
<div class="warn"><b>Limites</b> : les figurants que A animait par formules (duels, téléphone, bras du parapluie) sont remis en scène avec les verbes de B, donc visibles autrement ; A est plus rapide par image (≈ 20,9 i/s annoncés contre 9,2) ; la musique de l'unifié est celle du brief de B (synthèse) avec des pas ajoutés ; aucune oreille humaine n'a validé le son ; les 17 expressions de A sont moins nombreuses que celles de B.</div>
<h2>Clip original « Dix mondes, dix genres »</h2>
<p>≈ 93 s, sans dialogue : comédie, romance, thriller noir, action (course, saut), épopée, survie, science-fiction, espace, chagrin, retrouvailles — dix mondes de A, quatorze ambiances de lumière,
caméras de B (plan large, deux plans, gros plan, suivi, travelling avant/arrière, orbite, grue, contre-plongée, caméra à l'épaule), expressions variées, musique et bruitages originaux (synthèse de B, bibliothèque d'échantillons désactivée).</p>
<div class="row clip">{clip_html or '<p>Les clips (16:9 et 9:16) sont livrés comme fichiers séparés.</p>'}</div>
{'<p class="warn">Copie de transport : les vidéos A et B de cette page sont recompressées (crf 25) pour passer la boîte aux lettres ; les originaux sont dans comparaison/. Ne pas juger la finesse sur ces deux copies.</p>' if transport else ''}
</main><script>
const V=['vA','vB','vU'].map(i=>document.getElementById(i));const sl=document.getElementById('sl'),tc=document.getElementById('tc');let timer=null;
function seek(t){{t=+t;V.forEach(v=>v.currentTime=t);sl.value=t;tc.textContent=t.toFixed(2)+' s'}}
function playAll(){{const t=V[2].currentTime;V.forEach(v=>v.currentTime=t);V.forEach(v=>v.play());if(!timer)timer=setInterval(()=>{{const t=V[2].currentTime;sl.value=t;tc.textContent=t.toFixed(2)+' s';V.slice(0,2).forEach(v=>{{if(Math.abs(v.currentTime-t)>0.12)v.currentTime=t}})}},250)}}
function pauseAll(){{V.forEach(v=>v.pause());clearInterval(timer);timer=null}}
</script></body></html>"""
    (out / 'index.html').write_text(page, encoding='utf-8')
    (out / 'mesures.json').write_text(json.dumps(dict(marche=pr, clips=dict(zip([c.name for c in clips], cp))), indent=1, ensure_ascii=False), encoding='utf-8')
    print('page :', out / 'index.html')


if __name__ == '__main__':
    main()
