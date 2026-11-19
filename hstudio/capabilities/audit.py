"""Capability audit of an episode (V3): every element the episode asks for, checked against the registry BEFORE the
validator repairs it. The validator still makes sure the render never fails, but nothing is replaced silently any
more: each gap is listed with its consequence ("cube gris", "action supprimée"...) in capabilities.json and in the log,
and the planner turns it into an extension request."""
from . import registry, planner

def audit_episode(ep, style='pixel3d', caps=None):
    caps = caps or registry.build(); gaps = []; used = set()
    def need(kind, name, where, consequence):
        if name is None: return
        name = str(name); used.add(f'{kind}:{name}')
        if not registry.has(caps, kind, name, style): gaps.append(dict(where=where, kind=kind, name=name, consequence=consequence))
    sets = ep.get('sets') or {}
    for sn, sp in sets.items():
        if not isinstance(sp, dict): continue
        typ = sp.get('type', 'room')
        if style == 'pixel3d' and typ not in ('room', 'composed'): need('place', typ, f'décor {sn}', 'pièce vide (type room)')
        for k_, kind in (('sky', 'sky'), ('weather', 'weather')):
            if sp.get(k_) and sp[k_] != 'none': need(kind, sp[k_], f'décor {sn}', 'ignoré')
        props = list(sp.get('props') or []) + [p for r in (sp.get('rooms') or []) for p in (r.get('props') or [])]
        for e in sp.get('elements') or []:
            if not isinstance(e, dict): continue
            need('element', e.get('kind'), f'décor {sn}', 'élément ignoré')
            if e.get('kind') == 'prop': props.append(e)
            if e.get('style'): need('style', e['style'], f'décor {sn}', 'style concrete')
            for f in ((e.get('roof') or {}).get('furniture') or []) if isinstance((e.get('roof') or {}).get('furniture'), list) else []:
                props.append(f if isinstance(f, dict) else {'type': f})
        for p in props:
            if isinstance(p, dict): need('prop', p.get('type'), f'décor {sn}', 'cube gris à la place')
    for k, s in enumerate(ep.get('shots') or []):
        if not isinstance(s, dict): continue
        tag = f'plan {k}'
        if style == 'pixel3d' and s.get('set') and s['set'] not in sets: need('place', s['set'], tag, 'décor par défaut')
        for a in s.get('actions') or []:
            if not isinstance(a, dict): continue
            need('action', a.get('do'), tag, 'action supprimée')
            if a.get('do') == 'gesture': need('gesture', a.get('name'), tag, 'geste supprimé')
            if a.get('do') == 'face': need('expression', a.get('name'), tag, 'expression neutre')
        for a in s.get('actors') or []:
            if isinstance(a, dict) and a.get('face'): need('expression', a['face'], tag, 'expression neutre')
        for o in s.get('objects') or []:
            if not isinstance(o, dict): continue
            need('effect', o.get('type'), tag, 'objet ignoré (rien n\'est dessiné)')
            if o.get('type') == 'mover' and o.get('thing'):
                kind, _, name = str(o['thing']).partition(':')
                need('creature' if kind == 'creature' else 'prop', name, tag, 'cube gris à la place' if kind != 'creature' else 'rien n\'est dessiné')
            if o.get('type') == 'prop': need('prop', o.get('kind'), tag, 'cube gris à la place')
        cam = s.get('camera') if isinstance(s.get('camera'), dict) else {}
        if cam.get('shot'): need('camera', cam['shot'], tag, 'plan medium')
        for c in s.get('sfx') or []:
            nm = c if isinstance(c, str) else (c or {}).get('name')
            need('sound', nm, tag, 'son supprimé')
        if (s.get('audio') or {}).get('music'): need('music', s['audio']['music'], tag, 'musique ignorée')
        if style == 'console' and isinstance(s.get('scene'), dict): need('console_scene', s['scene'].get('type', 'door'), tag, 'scène porte')
    if ep.get('music'): need('music', ep['music'], 'épisode', 'musique horror')
    for cid, lk in (ep.get('cast') or {}).items():
        if isinstance(lk, dict):
            kd = lk.get('kind') or lk.get('preset')
            if kd and kd != 'creature':
                if f'creature:{kd}' in caps: need('creature', kd, f'personnage {cid}', 'apparence par défaut')
                else: need('character', kd, f'personnage {cid}', 'apparence par défaut')
            if lk.get('ref'): need('character', lk['ref'], f'personnage {cid}', 'apparence par défaut')
    req = planner.plan('', ep.get('requires') or [], style, caps) if ep.get('requires') else None
    return dict(style=style, used=sorted(used), gaps=gaps, requires=req, ok=not gaps and not (req and req['counts'].get('missing')))

def format_fr(rep):
    if rep['ok']: return f"Capacités : {len(rep['used'])} éléments utilisés, tous disponibles."
    out = [f"Capacités : {len(rep['used'])} éléments utilisés, {len(rep['gaps'])} manquant(s) :"]
    for g in rep['gaps'][:30]: out.append(f"  [MANQUE] {g['where']} : {g['kind']} « {g['name']} » -> {g['consequence']}")
    if rep.get('requires') and rep['requires']['counts'].get('missing'):
        out.append('  besoins déclarés manquants : ' + ', '.join(n['kind'] + ':' + n['name'] for n in rep['requires']['needs'] if n['status'] == 'missing'))
    return '\n'.join(out)

def report_project(ep_raw, style, text='', log=print):
    """audit of the raw episode + plan of the story text -> dict for capabilities.json, logged in French"""
    caps = registry.build()
    rep = dict(audit=audit_episode(ep_raw, style, caps), plan=planner.plan(text, ep_raw.get('requires') or [], style, caps) if text else None)
    log(format_fr(rep['audit']))
    if rep['plan'] and rep['plan']['counts'].get('missing'):
        log('Le texte demande aussi : ' + ', '.join(n['kind'] + ':' + n['name'] for n in rep['plan']['needs'] if n['status'] == 'missing') + ' (absent du moteur, voir capabilities.json)')
    return rep
