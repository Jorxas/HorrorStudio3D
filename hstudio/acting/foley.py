"""Foley from the acting timeline (both engines): every foot contact, pick-up, sit-down or door gets its sound at the
exact frame of the action. Levels stay low: the mixer ducks them under the voice like every sound effect."""

STEP = {'wood': 'step_wood', 'plank_dock': 'step_wood', 'carpet': 'step', 'tiles': 'step_hard', 'checker': 'step_hard', 'linoleum': 'step_hard',
        'concrete': 'step_hard', 'marble': 'step_hard', 'asphalt': 'step_hard', 'road': 'step_hard', 'stone': 'step_hard', 'cobble': 'step_hard',
        'grass': 'step_grass', 'moss': 'step_grass', 'leaves': 'step_grass', 'dirt': 'step_grass', 'mud': 'step_grass', 'sand': 'step_grass', 'snow': 'step_grass'}

def cues(events):
    """events: [(t_abs, kind, who, data)] -> [{name, t, gain, pan}]"""
    out = []
    for (t, kind, who, d) in events:
        d = d or {}
        if kind == 'step':
            out.append(dict(name=STEP.get(d.get('surface'), 'step'), t=t, gain=.42 if d.get('run') else .3, pan=float(d.get('pan', 0.))))
        elif kind in ('pickup', 'put'): out.append(dict(name='paper' if str(d.get('item', '')).startswith(('lettre', 'letter', 'carte', 'map')) else 'pickup', t=t, gain=.5 if kind == 'pickup' else .35))
        elif kind == 'give': out.append(dict(name='paper' if str(d.get('item', '')).startswith(('lettre', 'letter', 'carte', 'map')) else 'pickup', t=t, gain=.4))
        elif kind in ('sit', 'stand'): out.append(dict(name='cloth', t=t, gain=.55 if kind == 'sit' else .4))
        elif kind == 'door_open':
            if not d.get('slow'): out.append(dict(name='door_handle', t=t - .25, gain=.55))
            out.append(dict(name='creak', t=t + .1, gain=.65 if d.get('slow') else .5))
        elif kind == 'door_close': out.append(dict(name='door_slam', t=t + .6, gain=.35))
        elif kind == 'door_slam': out.append(dict(name='door_slam', t=t + .15, gain=.8))
        elif kind == 'react' and d.get('kind') in ('startle', 'gasp'): out.append(dict(name='breath', t=t, gain=.3))
        elif kind == 'thunder': out.append(dict(name='thunder', t=t, gain=float(d.get('gain', .9))))
        elif kind == 'sfx':
            c = dict(name=d.get('name', 'click'), t=t, gain=float(d.get('gain', .7)))
            if d.get('dur') is not None: c['dur'] = float(d['dur'])
            out.append(c)
        elif kind == 'jump': out.append(dict(name='jump_push', t=t - .05, gain=.45))
        elif kind == 'land': out.append(dict(name='land', t=t, gain=min(.8, .4 + .15 * float(d.get('height', .5)))))
        elif kind == 'climb': out += [dict(name='cloth', t=t, gain=.5), dict(name='breath', t=t + .2, gain=.25)]
        elif kind == 'fall': out.append(dict(name='whoosh', t=t, gain=.4))
    return out
