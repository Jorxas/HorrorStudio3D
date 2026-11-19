"""« La marche » (61 s, 9:16, no voice) on the unified engine: B directs, A paints.

Sources, both existing: engine A's `film_marche.js` (the ten worlds in the painter, the cast and its accessories, the camera
table, expressions per world, footprints, the final flash) and Horror Studio's `tools/la_marche_worlds.py` (the same brief
as data: the camera marks, Noe at 0.95 m/s through ten worlds, dissolves of 1.2 s, a score).  Here the two meet in an
EPISODE of the unified DSL: every world is one shot; Noe and the bystanders are moved by B's régie (paths, speeds, faces,
gestures); the camera is the brief's table (`orbit_keys`), evaluated on absolute time so two worlds that dissolve into
each other share it; the painter is A.

What is translated and what is not (honest list in docs/VOXELGPU.md): bystanders that A animated by hand-written formulas
(a man texting on a bench, duelling soldiers, the umbrella carriers' raised arm) are re-staged with B's verbs and gestures,
so they look like the same idea, not the same pose.
"""
V = .95
T0 = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54]
END = 61.
DIS = 1.2
LEAD = 1.5
WORLDS = ['ville', 'parc', 'automne', 'pluie', 'glace', 'feu', 'bataille', 'invasion', 'vaisseau', 'lune']
CAM = [[0, .30, 7.5, 1.7, 1.6, 46], [6, .70, 6.2, 1.5, 1.5, 46], [14, 1.10, 5.8, 1.4, 1.45, 46], [22, .85, 5.6, 1.6, 1.5, 46], [27, 1.45, 5.8, 2.1, 1.25, 46],
       [30, .50, 6.0, 1.0, 1.7, 48], [38, .95, 6.8, 1.6, 1.4, 48], [45, .55, 6.5, .8, 2.2, 52], [52, 1.30, 5.2, 1.5, 1.5, 48], [57, 1.50, 6.0, 3.1, .85, 46], [61, 2.45, 8.5, 2.6, 1.2, 48]]
EXPR = ['neutral', 'happy', 'relief', 'sad', 'determined', 'scared', 'grit', 'surprised', 'neutral', 'determined']
PRINTS = {'glace': ('#34445e', .9, 0.), 'lune': ('#16161a', 1., 0.), 'bataille': ('#1e1208', .9, 0.), 'automne': ('#3a2208', .6, 0.), 'parc': ('#5a4020', .6, .035)}


def _mid(i): return (T0[i] + (T0[i + 1] + DIS if i < 9 else END)) / 2


def _dur(i): return (T0[i + 1] if i < 9 else END) - T0[i]


def _start(x_at_0, v):
    """x to start from so that the body is at x_at_0 when the stage becomes visible (the ramp of the walk is over)"""
    return x_at_0 - v * (LEAD - .225)


def _end(x_at_0, v, i): return x_at_0 + v * (_dur(i) + (DIS if i < 9 else 0) + 2.)


def walker(aid, i, x_at_0, z, v, face='neutral', gesture=None):
    """a character that crosses the stage at constant speed v (m/s, sign = direction along x)"""
    s = x_at_0 - v * (LEAD - .225); e = x_at_0 + v * (_dur(i) + (DIS if i < 9 else 0) + 2.)
    a = dict(id=aid, at=[s, z], facing='+x' if v > 0 else '-x', face=face)
    if gesture: a['gesture'] = gesture
    return [a], [dict(who=aid, do='walk_to', to=[e, z], speed=abs(v), at=0)]


def episode(music_wav=None):
    casts = {'noe': {'preset': 'noe'}, 'lina': {'preset': 'lina'},
             **{f'npc{k}': {'preset': 'npc', 'variant': k} for k in (0, 1, 2, 4, 6, 7, 9)},
             **{f'um{k}': {'preset': 'npc', 'variant': k, 'accessories': ['umbrella'], 'umbrella_color': c} for k, c in ((0, '#2a2a30'), (1, '#c83a3a'), (2, '#3a6ac8'))},
             **{f'sol{k}': {'preset': 'npc', 'variant': k, 'accessories': ['sword', 'shield', 'helmet'], 'shield_color': '#c02a2a' if k % 2 else '#2a4ac0'} for k in range(3, 9)},
             **{f'al{k}': {'preset': 'alien'} for k in range(3)}}
    shots = []
    for i, w in enumerate(WORLDS):
        x0 = (T0[i] - _mid(i)) * V
        actors, actions = walker('noe', i, x0, 0., V, EXPR[i])

        def add(a, b): actors.extend(a); actions.extend(b)

        def t(d): return d + LEAD                       # time inside the shot (the lead comes first)
        if i == 0:
            add(*walker('npc0', i, 7, -1.2, -1.1)); add(*walker('npc1', i, -9, -11.4, 1.0, 'happy')); add(*walker('npc2', i, 9, -12.0, -.9))
            actors.append(dict(id='npc6', at=[2.6, -1.55], facing=-17., face='neutral', gesture='hold_up'))
            actions += [dict(who='npc6', do='face', name='happy', at=t(2.5))]
        if i == 1:
            add(*walker('lina', i, x0 + .45, -1.05, V, 'happy'))
            actions += [dict(who='lina', do='look_at', target='noe', at=t(1.5), dur=2.0), dict(who='noe', do='look_at', target='lina', at=t(2.2), dur=2.0)]
            actors.append(dict(id='npc4', on='banc2', face='happy'))
        if i == 2:
            stop = 3.0; xs = x0 + .45 + V * stop
            actors.append(dict(id='lina', at=[x0 + .45 - V * (LEAD - .225), -1.05], facing='+x', face='relief'))
            actions += [dict(who='lina', do='walk_to', to=[xs, -1.05], speed=V, at=0), dict(who='lina', do='turn_to', target=[xs + 5, -3.0]), dict(who='lina', do='face', name='sad'),
                        dict(who='lina', do='gesture', name='wave', dur=3.0), dict(who='noe', do='face', name='sad', at=t(3.6))]
        if i == 3:
            for k in range(3): add(*walker(f'um{k}', i, 6 + k * 3.5, -1.4 - k * .5, -1.0, 'neutral', 'extend'))
        if i == 5:
            actors.append(dict(id='npc7', at=[8 + 22 / 7 * (LEAD - .3), -6.], facing='-x', face='scared'))
            actions += [dict(who='npc7', do='run_to', to=[8 - 22 - 6, -6.], speed=22 / 7, at=0)]
        if i == 6:
            for n, (a_, b_, x, z) in enumerate([(3, 4, -2.2, -2.6), (5, 6, 1.8, -3.2), (7, 8, -.4, -5.2)]):
                actors += [dict(id=f'sol{a_}', at=[x - .75, z], facing='+x', face='shout' if n % 2 else 'grit'), dict(id=f'sol{b_}', at=[x + .75, z], facing='-x', face='grit' if n % 2 else 'shout')]
                for who, ph in ((f'sol{a_}', 0.), (f'sol{b_}', .55)):
                    for k in range(int(_dur(i) // 1.1) + 3): actions.append(dict(who=who, do='gesture', name='knock', at=t(ph + k * 1.1), dur=.5))
        if i == 7:
            for k, (ox, oz) in enumerate([(-.9, -2.6), (-5.2, -2.3), (-5.2, -3.7)]):
                actors.append(dict(id=f'al{k}', at=[x0 + ox - V * (LEAD - .225), oz], facing='+x', face='surprised' if k == 1 else 'neutral'))
                actions.append(dict(who=f'al{k}', do='walk_to', to=[x0 + ox + V * 9, oz], speed=V * .93, at=0))
            actions.append(dict(who='al0', do='gesture', name='point', dur=6.0, at=t(0)))
            for k in range(3): add(*walker(f'npc{k}', i, 9 + .8 * k * 3.4, -1.6 - k * 1.4, -3.4, 'shocked'))
        if i == 8: add(*walker('npc9', i, 6, -2.4, -.9, 'happy'))
        shot = dict(stage=w, dur=_dur(i), lead=LEAD, dissolve=DIS if i else 0., actors=actors, actions=actions, focus_actor='noe',
                    camera=dict(rig='orbit_keys', on=['noe'], keys=CAM, look_dx=.25, roll_deg=.7, roll_period=16.), dof=.35, mblur=.15, shadow_s=14)
        if w in PRINTS: c, o, y = PRINTS[w]; shot['prints'] = dict(color=c, opacity=o, y=y, actor='noe')
        shots.append(shot)
    return dict(title='La marche', genre='neutral', fps=24, aspect='9:16', duration=END, casts=casts, shots=shots,
                fx=[dict(type='fade', t0=0, t1=.8, **{'from': 0, 'to': 1}), dict(type='flash', t0=59., t1=61., **{'from': 0, 'to': 1}, exposure=1.5)],
                audio=dict(wav=music_wav, wav_gain=1.0, foley=dict(steps=True, gain=.22)) if music_wav else {})
