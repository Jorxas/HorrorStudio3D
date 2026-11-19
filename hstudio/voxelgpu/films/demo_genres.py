"""« Dix mondes, dix genres » : original clip (about 97 s), no dialogue, no voice, music and sound effects synthesised here.

Written for the unified engine to show what it can do that neither original engine does alone: ONE script in B's DSL
(régie: runs, sits, jumps, hugs, gestures, reactions, expressions; cinematographer: wide / two-shot / close / follow /
dolly / orbit / crane / low angle, handheld) painted by A's characters, faces, hands, worlds and post-processing, with
the light of each genre (mood) on top of the world's own, and cuts as well as dissolves.

Ten scenes, ten genres: comedy, romance, noir thriller, action, epic, survival, science fiction, space opera, sorrow, reunion.
Both formats come from the same episode: `episode()` then `director.build(ep, '16:9' | '9:16')`.
"""
CASTS = {
    'tom': {'preset': 'noe'}, 'lea': {'preset': 'lina'},
    'ada': {'preset': 'npc', 'variant': 1}, 'leo': {'preset': 'npc', 'variant': 2},
    'max': {'preset': 'npc', 'variant': 3},
    'sol3': {'preset': 'npc', 'variant': 3, 'accessories': ['sword', 'shield', 'helmet'], 'shield_color': '#2a4ac0'},
    'sol4': {'preset': 'npc', 'variant': 4, 'accessories': ['sword', 'shield', 'helmet'], 'shield_color': '#c02a2a'},
    'al0': {'preset': 'alien'}, 'al1': {'preset': 'alien'},
}


def shot(stage, dur, camera, actors=None, actions=None, mood=None, dissolve=0., **kw):
    s = dict(stage=stage, dur=dur, camera=camera, actors=actors or [], actions=actions or [], dissolve=dissolve)
    if mood: s['mood'] = mood
    s.update(kw); return s


def episode():
    S = []
    # ---- 1. COMEDY (city, morning): Tom is late, Lea is not amused, then she laughs
    S += [
        shot('ville', 4.5, dict(shot='wide', on=['tom', 'lea']), mood='comedy',
             actors=[dict(id='tom', at=[-9, .6], facing='+x', face='worried'), dict(id='lea', at=[1.5, .2], facing='-x', face='angry', gesture='cross_arms')],
             actions=[dict(who='tom', do='run_to', to='lea', stop_dist=1.4, at=.2), dict(who='tom', do='react', kind='sigh', at=3.6)]),
        shot('ville', 2.5, dict(shot='close', on=['lea'], move='dolly_in', amount=.4), mood='comedy',
             actions=[dict(who='lea', do='face', name='angry'), dict(who='lea', do='face', name='smirk', at=1.6)]),
        shot('ville', 3.2, dict(shot='two_shot', on=['tom', 'lea'], move='dolly_out', amount=.4), mood='comedy',
             actions=[dict(who='tom', do='gesture', name='surrender', at=.2, dur=1.6), dict(who='tom', do='face', name='happy', at=.4),
                      dict(who='lea', do='react', kind='laugh', at=1.0), dict(who='tom', do='react', kind='cheer', at=2.0)]),
    ]
    # ---- 2. ROMANCE (park, golden hour)
    S += [
        shot('parc', 5.0, dict(shot='wide', on=['ada', 'leo']), mood=[['romance', .9], ['dusk', .6]], dissolve=1.0,
             actors=[dict(id='ada', on='banc2', face='happy', gesture='hold'), dict(id='leo', at=[-6.5, .2], facing='+x', face='nervous')],
             actions=[dict(who='leo', do='walk_to', to='ada', stop_dist=1.2, at=.3), dict(who='leo', do='gesture', name='wave', at=3.9, dur=1.0),
                      dict(who='ada', do='look_at', target='leo', at=2.2, dur=2.5)]),
        shot('parc', 5.0, dict(shot='two_shot', on=['ada', 'leo'], move='dolly_in', amount=.5), mood=[['romance', .9], ['dusk', .6]],
             actions=[dict(who='leo', do='face', name='shy'), dict(who='leo', do='gesture', name='hand_chest', at=.4, dur=1.8), dict(who='ada', do='face', name='love', at=1.4),
                      dict(who='ada', do='gesture', name='hug', at=2.8, dur=2.0), dict(who='leo', do='gesture', name='hug', at=3.0, dur=1.9)]),
    ]
    # ---- 3. NOIR THRILLER (rain, night)
    S += [
        shot('pluie', 5.0, dict(shot='full', on=['max'], move='follow', angle='low'), mood='noir', dissolve=1.0,
             actors=[dict(id='max', at=[-8, .3], facing='+x', face='worried', gesture='pockets')],
             actions=[dict(who='max', do='walk_to', to=[3, .3], speed='slow', at=.2), dict(who='max', do='look_around', at=3.5)]),
        shot('pluie', 3.0, dict(shot='close', on=['max'], move='dolly_in', amount=.5), mood='noir',
             actions=[dict(who='max', do='react', kind='startle', at=.7), dict(who='max', do='face', name='scared', at=.7), dict(who='max', do='look_at', target='offscreen_right', at=.5, dur=2.0)]),
        shot('pluie', 3.0, dict(shot='wide', on=['max'], move='handheld', amount=.8), mood='noir',
             actions=[dict(who='max', do='run_to', to='offscreen_left', at=.3)]),
    ]
    # ---- 4. ACTION (burning ruins)
    S += [
        shot('feu', 4.2, dict(shot='full', on=['leo'], move='follow'), mood='adventure', dissolve=.6,
             actors=[dict(id='leo', at=[-9, -.5], facing='+x', face='determined')],
             actions=[dict(who='leo', do='run_to', to=[-1, -.5], at=0), dict(who='leo', do='jump', to=[2.6, -.5], hang=1.4, style='leap')]),
        shot('feu', 2.4, dict(shot='close', on=['leo'], angle='low'), mood='adventure', look=dict(exposure=1.6),
             actions=[dict(who='leo', do='face', name='furious'), dict(who='leo', do='gesture', name='victory', at=.6, dur=1.4)]),
        shot('feu', 3.4, dict(shot='wide', on=['leo'], move='handheld', amount=1.0), mood='adventure',
             actions=[dict(who='leo', do='react', kind='flinch', at=.5), dict(who='leo', do='run_to', to=[9, -.5], at=1.0)]),
    ]
    # ---- 5. EPIC (battlefield)
    S += [
        shot('bataille', 5.5, dict(shot='two_shot', on=['sol3', 'sol4'], move='orbit', amount=1.0), mood=['adventure', 'warm'], dissolve=1.0,
             actors=[dict(id='sol3', at=[-.8, -.5], facing='+x', face='grit'), dict(id='sol4', at=[.8, -.5], facing='-x', face='shout')],
             actions=[dict(who=w, do='gesture', name='knock', at=.3 + k * 1.0 + (0 if w == 'sol3' else .5), dur=.5) for k in range(5) for w in ('sol3', 'sol4')]),
        shot('bataille', 3.5, dict(shot='close', on=['sol3'], angle='low'), mood=['adventure', 'warm'],
             actions=[dict(who='sol3', do='face', name='shout'), dict(who='sol3', do='gesture', name='cheer', at=.5, dur=2.5)]),
    ]
    # ---- 6. SURVIVAL (glacier)
    S += [
        shot('glace', 4.0, dict(shot='wide', on=['ada'], move='crane_up', amount=.8), mood='drama', dissolve=1.0,
             actors=[dict(id='ada', at=[-3, .2], facing='+x', face='sad', gesture='shiver')],
             actions=[dict(who='ada', do='walk_to', to=[2, .2], speed='slow', at=.2)]),
        shot('glace', 4.0, dict(shot='close', on=['ada'], move='dolly_in', amount=.4), mood='drama',
             actions=[dict(who='ada', do='face', name='determined', at=1.8), dict(who='ada', do='gesture', name='cross_arms', at=.2, dur=3.0)]),
    ]
    # ---- 7. SCIENCE FICTION (invasion)
    S += [
        shot('invasion', 4.5, dict(shot='full', on=['tom', 'al0', 'al1'], angle='low'), mood='scifi', dissolve=1.0,
             actors=[dict(id='tom', at=[-2, .3], facing='+x', face='surprised'), dict(id='al0', at=[8, -.3], facing='-x'), dict(id='al1', at=[10, -1.6], facing='-x')],
             actions=[dict(who='al0', do='walk_to', to='tom', stop_dist=3.0, speed='slow', at=.2), dict(who='al1', do='walk_to', to=[3.5, -1.6], speed='slow', at=.4),
                      dict(who='tom', do='react', kind='gasp', at=.6), dict(who='tom', do='face', name='scared', at=.8), dict(who='al0', do='gesture', name='point', at=2.4, dur=1.8)]),
        shot('invasion', 3.5, dict(shot='close', on=['tom'], move='dolly_out', amount=.5), mood='scifi',
             actions=[dict(who='tom', do='gesture', name='surrender', at=.2, dur=3.0), dict(who='tom', do='face', name='shocked', at=1.0)]),
    ]
    # ---- 8. SPACE (ship interior)
    S += [
        shot('vaisseau', 4.5, dict(shot='medium', on=['lea'], move='dolly_in', amount=.5), mood='scifi', dissolve=1.0,
             actors=[dict(id='lea', at=[0, .3], facing='+z', face='worried')],
             actions=[dict(who='lea', do='gesture', name='think', at=.3, dur=2.0), dict(who='lea', do='face', name='surprised', at=2.6), dict(who='lea', do='look_at', target=[6, 1.8, -2], at=2.4, dur=2)]),
        shot('vaisseau', 3.0, dict(shot='wide', on=['lea']), mood='scifi',
             actions=[dict(who='lea', do='walk_to', to=[5, -.2], speed='hurry', at=.2), dict(who='lea', do='face', name='joy', at=1.4)]),
    ]
    # ---- 9. SORROW (the Moon, night)
    S += [
        shot('lune', 5.0, dict(shot='establishing', on=['tom'], move='crane_down', amount=.8), mood='night', dissolve=1.2,
             actors=[dict(id='tom', at=[-4, .2], facing='+x', face='sad')],
             actions=[dict(who='tom', do='walk_to', to=[0, .2], speed='slow', at=.2), dict(who='tom', do='sit', at=3.4)]),
        shot('lune', 4.5, dict(shot='close', on=['tom'], move='dolly_in', amount=.4), mood='night', look=dict(exposure=1.5),
             actions=[dict(who='tom', do='look_at', target=[0, 40, -80], at=.2, dur=3.0), dict(who='tom', do='face', name='crying', at=1.0), dict(who='tom', do='face', name='smile_sad', at=3.2)]),
    ]
    # ---- 10. REUNION (autumn)
    S += [
        shot('automne', 4.0, dict(shot='wide', on=['tom', 'lea']), mood=['warm', 'drama'], dissolve=1.2,
             actors=[dict(id='tom', at=[-7, .3], facing='+x', face='relief'), dict(id='lea', at=[7, .3], facing='-x', face='surprised')],
             actions=[dict(who='tom', do='run_to', to='lea', stop_dist=1.0, at=.3), dict(who='lea', do='run_to', to='tom', stop_dist=1.0, at=.5)]),
        shot('automne', 5.5, dict(shot='two_shot', on=['tom', 'lea'], move='dolly_in', amount=.6), mood=['warm', 'drama'],
             actions=[dict(who='tom', do='gesture', name='hug', at=.3, dur=4.0), dict(who='lea', do='gesture', name='hug', at=.4, dur=4.0), dict(who='lea', do='face', name='joy', at=.8), dict(who='tom', do='face', name='joy', at=.8)]),
    ]
    dur = sum(s['dur'] for s in S)
    t = 0.; starts = []
    for s in S: starts.append(t); t += s['dur']
    # genre captions at the first shot of each scene
    labels = [('COMÉDIE', 0), ('ROMANCE', 3), ('THRILLER', 5), ('ACTION', 8), ('ÉPOPÉE', 11), ('SURVIE', 13), ('SCIENCE-FICTION', 15), ('ESPACE', 17), ('CHAGRIN', 19), ('RETROUVAILLES', 21)]
    caps = [dict(t0=round(starts[i] + .3, 2), t1=round(starts[i] + 2.4, 2), text=name) for name, i in labels]
    sc = [starts[i] for _, i in labels]
    music = [dict(t0=max(0, a - .5), t1=min(dur, b + .8), style=st, gain=g, seed=n, fade=1.0) for n, (a, b, st, g) in enumerate(zip(sc, sc[1:] + [dur], ['comedy', 'romance', 'mystery', 'action', 'epic', 'sad', 'mystery', 'calm', 'sad', 'romance'], [.55, .55, .6, .55, .55, .6, .55, .55, .6, .6]))]
    amb = [dict(t0=sc[0], t1=sc[1], name='city', gain=.25), dict(t0=sc[1], t1=sc[2], name='park', gain=.3), dict(t0=sc[2], t1=sc[3], name='rain', gain=.35),
           dict(t0=sc[3], t1=sc[4], name='campfire', gain=.3), dict(t0=sc[4], t1=sc[5], name='crowd', gain=.15), dict(t0=sc[5], t1=sc[6], name='wind', gain=.35),
           dict(t0=sc[6], t1=sc[7], name='space', gain=.25), dict(t0=sc[7], t1=sc[8], name='space', gain=.2), dict(t0=sc[8], t1=sc[9], name='space', gain=.2), dict(t0=sc[9], t1=dur, name='countryside', gain=.3)]
    at = lambda i, d: round(starts[i] + d, 2)
    sfx = [dict(t=at(1, .2), name='boing', gain=.5), dict(t=at(2, 1.0), name='laugh', gain=.5), dict(t=at(4, 3.9), name='pop', gain=.4),
           dict(t=at(6, 2.6), name='thunder', gain=.8), dict(t=at(6, .7), name='heartbeat', gain=.7), dict(t=at(7, .3), name='whoosh', gain=.4),
           dict(t=at(8, 2.3), name='jump_push', gain=.6), dict(t=at(8, 3.5), name='land', gain=.6), dict(t=at(10, .4), name='explosion', gain=.8),
           dict(t=at(11, .4), name='sword_clash', gain=.6), dict(t=at(11, 1.4), name='sword_clash', gain=.6), dict(t=at(11, 2.4), name='sword_clash', gain=.6), dict(t=at(11, 3.4), name='sword_clash', gain=.6),
           dict(t=at(12, .8), name='cheer', gain=.4), dict(t=at(15, .2), name='riser', gain=.6), dict(t=at(15, 2.6), name='impact', gain=.7),
           dict(t=at(18, 1.4), name='success', gain=.5), dict(t=at(19, 3.2), name='sting', gain=.4), dict(t=at(22, .9), name='ding', gain=.5)]
    sfx = [c for c in sfx if c['t'] < dur]
    return dict(title='Dix mondes, dix genres', genre='neutral', fps=24, duration=round(dur, 3), casts=CASTS, shots=S,
                fx=[dict(type='fade', t0=0, t1=.8, **{'from': 0, 'to': 1}), dict(type='fade', t0=dur - 2.0, t1=dur, **{'from': 1, 'to': 0}),
                    dict(type='flash', t0=at(10, .4), t1=at(10, 1.4), color='#ffb060', peak=.55, **{'from': 1, 'to': 0}), dict(type='shake', t0=at(8, 0), t1=at(8, 4.2), amount=.6),
                    dict(type='shake', t0=at(10, 0), t1=at(10, 3.4), amount=1.0)],
                captions=caps, caption_style=dict(size=.06, y=.12, color='#ffffff', hi='#ffd84a'),
                audio=dict(music=music, ambience=amb, sfx=sfx, foley=dict(steps=True, gain=.35)))
