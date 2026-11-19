"""Scène de test des figurants : une rue de nuit, deux personnages qui parlent au premier plan, des figurants qui vivent la rue, puis un monstre apparaît au fond et tout le monde réagit.
`episode(extras=True, spacing=True, count=10)` -> épisode VOXEL (utilisé par la planche, l'audit et les tests)."""
import copy


def episode(cam='wide', extras=True, spacing=True, count=10, seed=3, dur=16., threat=8.0, keep=3.0, fps=24, monster=True, place='city_street'):
    leads = {'noe': {'preset': 'noe'}, 'lina': {'preset': 'lina'}}
    shots = [dict(set='rue', dur=dur, mood='neutral', env={'ambient': 2.3, 'key': 1.0, 'fog': 0.004}, camera=dict(shot=cam, on=['noe', 'lina'], **{'from': [0.0, 7.0]}),
                  actors=[dict(id='noe', at=[-1.6, 0.5], facing=[0.2, 0.5], face='worried'), dict(id='lina', at=[0.6, 0.5], facing=[-1.6, 0.5], face='neutral')],
                  speech=[[0.6, 3.2, 'noe'], [3.5, 6.4, 'lina'], [6.7, 9.4, 'noe'], [10.4, 13.6, 'lina']], actions=[])]
    ep = dict(title='figurants', genre='horror', casts=dict(leads), sets={'rue': {'type': place, 'sky': 'night'}}, shots=shots, duration=dur, fps=fps)
    if monster:
        ep['casts']['slender'] = {'kind': 'creature', 'archetype': 'slender', 'height': 2.7}
        shots[0]['actors'].append(dict(id='slender', at=[1.5, -9.], facing='+z', visible=[threat - .2, 1e9]))
    if spacing: ep['spacing'] = True
    if extras:
        ex = dict(count=count, troupe='auto', seed=seed, keep_clear=keep, beats=[dict(shot=0, do='flee', **{'from': 'slender'}, at=threat + .6)] if monster else [])
        ep['extras'] = ex
    return ep
