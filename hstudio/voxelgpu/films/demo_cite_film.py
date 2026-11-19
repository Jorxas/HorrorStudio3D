"""« Le Dernier Noyau » : the episode (casts, world tables, props, cameras, sound) built on the blocking of `demo_cite_story.py`.
`episode()` -> a dict for `director.build` (blocking path); `python tools/demo_cite_film.py` renders it. Nothing here draws a pixel and nothing is random."""
import copy, hashlib, json, math
from pathlib import Path
from .. import blocking as BLK, camplan as CP, stagegeo, localvoice as LV
from . import demo_cite as D, demo_cite_cast as CAST, demo_cite_story as S
from .demo_cite import c, a_, s_, PI, WORK, LINES
from ...remake.dsl import k as _k, cam

ASPECT = '9:16'
SPEAKER = {l['who']: l['speaker'] for l in LINES}
FPS = 30


# ------------------------------------------------------------------------------------------------------------------ world tables
def swing_table(*windows):
    iv = sorted(windows); m = []
    for a, b in iv:
        if m and a - .5 <= m[-1][1] + .5: m[-1] = (m[-1][0], max(m[-1][1], b))
        else: m.append((a, b))
    return D.swing((0, 0), *[p for (a, b) in m for p in ((a - .5, 0), (a, 1), (b, 1), (b + .5, 0))])


def doors(F):
    ev = F.ev
    return {'cafe_porte': swing_table(ev['door1'], ev['door2'], ev['door3']), 'monte_charge': swing_table(ev['lift_open']), 'lift_toit': swing_table(ev['lift_roof'])}


def world_env(F):
    A = F.notes; dr = doors(F); cn = A['city_night']; T0 = A['launch']
    cars = []
    for i, (t0, v) in enumerate([(2.0, 9.), (8.0, -8.), (30.0, 9.5), (47.0, -9.), (63.0, 8.5), (79.0, -9.)]): cars.append(dict(t0=t0, x0=(-66. if v > 0 else 66.), v=v, lane=(.8 if v > 0 else 3.2)))
    return dict(door_cafe=dr['cafe_porte'], lift_door=dr['monte_charge'], day=[[0, 1.], [cn - .05, 1.], [cn, .2]], lit=[[0, 0.], [cn, .15], [cn + 3.5, 1.]], lamps=[[0, 0.], [cn, 0.], [cn + 3.5, 1.]],
                clock=[[0, 11 * 60 + 27], [27, 11 * 60 + 40], [74, 11 * 60 + 55], [A['launch'], 12 * 60], [A['end'], 12 * 60 + 1]], cafe=1., cars=cars, alley=1)


def astro_env(F):
    A = F.notes; dr = doors(F); L0 = A['launch']; b0 = A['board']
    return dict(lift_door_roof=dr['lift_toit'], alt=[[0, 0.], [L0 + 3.0, .05], [L0 + 8.5, .55], [L0 + 11.5, 1.]], lift=[[0, 0.], [L0, 0.], [L0 + 3., 4.], [L0 + 6., 28.], [L0 + 9., 90.], [L0 + 11.5, 200.]],
                thrust=[[0, 0.], [b0 + .4, 0.], [b0 + 1.3, 1.], [L0 + 12, 1.]], hatch=[[0, 1.], [b0 - .2, 1.], [b0 + .6, 0.]])


def selene_env(F):
    A = F.notes
    return dict(beacon=[[0, 0.], [A['beacon_on'], 0.], [A['beacon_on'] + 1.4, 1.]], hatch_moon=[[0, 1.]])


# ------------------------------------------------------------------------------------------------------------------ casts
def casts_of(F):
    out = {}
    for aid, sp in F.actors.items():
        if sp.get('role') == 'extra': ec = CAST.extra_cast(sp['idx']); ec['worlds'] = sp['worlds']; out[aid] = ec; continue
        base = aid.split('_')[0]; d = copy.deepcopy(CAST.HEROES[base]); d['worlds'] = sp['worlds']; out[aid] = d
    held = {}
    for b in F.beats:
        if b['do'] == 'take': held.setdefault(b['who'], []).append((b['t'], float(b.get('until', 1e9)), b.get('item', 'mallette'), b.get('hand', 'R')))
        elif b['do'] == 'draw': held.setdefault(b['who'], []).append((b['t'] + .25, float(b.get('until', 1e9)), 'epee', b.get('hand', 'L')))
    boxes = {'mallette': D.CASE_PX, 'epee': D.SWORD_PX}; A = F.notes
    held.setdefault('ines', []).append((0., A['place'], 'mallette', 'R'))                                       # she runs in with the case
    held.setdefault('ines_r', []).append((0., 1e9, 'mallette', 'L')); held.setdefault('ines_m', []).append((0., A['insert'], 'mallette', 'L'))
    for aid, lst in held.items():
        out[aid]['extras'] = [{'bone': 'hand' + h, 'at': [0, -1.2, 1.5], 't0': t0, 't1': t1, 'boxes': boxes[item]} for (t0, t1, item, h) in lst]
    return out


# ------------------------------------------------------------------------------------------------------------------ props (objects of the world that move or appear)
def props_of(F):
    A = F.notes; P = {'cite': [], 'astroport': [], 'selene': []}
    case = lambda at, t0, t1, ry=0.: {'type': 'mover', 'boxes': D.CASE_W, 'track': [[0, at[0], at[1] - .0, at[2], ry]], 't0': t0, 't1': t1}
    P['cite'].append(case((c(-3.2), 1.05, -3.0), A['place'], A['steal'], .0))                                    # on the tall table
    P['cite'].append(case((c(-7.3), 1.12, -11.1), A['cab_put'], A['cab_take'] + .1, .0))                         # on the cabinet
    sw = lambda track, t0, t1: {'type': 'mover', 'boxes': D.SWORD_W, 'track': track, 't0': t0, 't1': t1}
    P['cite'].append(sw([[0, c(-6.9), 1.9, -15.22, PI / 2 + PI / 2, -PI / 2, 0.]], 0., A['take_sword']))         # epee_a on the rack until Malo takes it
    P['cite'].append(sw([[0, c(-6.1), 1.9, -15.22, PI, -PI / 2, 0.]], 0., 1e9))                                    # epee_b stays on the rack
    p0 = A['p_catch']; t_th, t_ca = A['throw'], A['catch']; mx, mz = c(-7.0), -14.5
    P['cite'].append(sw([[t_th, mx, 1.45, mz, 0.4, 0., 0.], [(t_th + t_ca) / 2, (mx + p0[0]) / 2, 2.0, (mz + p0[2]) / 2, 0.4 + 3., 0.3, 0.], [t_ca, p0[0], p0[1], p0[2], 0.4 + 6., 0., 0.]], t_th, t_ca))    # the thrown sword
    t_d = A['disarm']; P['cite'].append(sw([[t_d, c(-5.0), 1.3, -10.95, 0., 0., 0.], [t_d + .25, c(-4.3), 1.7, -12.0, 3., 1., .5], [t_d + .55, c(-3.3), .06, -13.1, 6., 0., 0.], [t_d + 1.0, c(-3.3), .06, -13.1, 6.3, 0., 0.]], t_d, 1e9))
    P['cite'].append(sw([[0, c(-7.3), 1.2, -10.4, PI / 2, 0., 0.]], A['sword_down'], 1e9))                     # Inès lays her sword on the cabinet
    P['astroport'].append({'type': 'mover', 'boxes': [], 'track': [[0, 0, 0, 0, 0]]})
    P['selene'].append(case((s_(8.0), 1.0, .72), A['insert'], 1e9, 0.))
    return P


def lights_of(F):
    A = F.notes; L = {'cite': [], 'astroport': [], 'selene': []}
    on = lambda t0, t1, i: [[0, 0], [t0, 0], [t0 + .1, i], [t1, i], [t1 + .1, 0]]
    L['cite'].append(dict(at=[c(-3.2), 1.5, -3.0], color='#7ad8ff', i=on(A['place'], A['steal'], 2.2), dist=3.2, decay=1.6))
    L['cite'].append(dict(at=[c(-7.3), 1.5, -11.1], color='#7ad8ff', i=on(A['cab_put'], A['cab_take'], 2.4), dist=3.4, decay=1.6))
    L['selene'].append(dict(at=[s_(8.0), 1.4, 1.2], color='#7ad8ff', i=on(A['insert'], A['end'] + 5, 3.0), dist=4.0, decay=1.6))
    return L


# ------------------------------------------------------------------------------------------------------------------ cameras
class Cams:
    def __init__(self, geo, C, sig=''):
        self.geo, self.C = geo, C; self.shots = []; self.log = []; self.fail = []; self.sig = sig; self.cfile = WORK / 'cams_shot_cache.json'
        self.cache = json.loads(self.cfile.read_text(encoding='utf-8')) if self.cfile.exists() else {}

    def add(self, sid, t0, t1, world, frame=None, fov=60., fixed=None, follow=None, cands=None, prefer=None, hint=None, drift=None, fovs=None, rs=None, shake=.05, env=None, why='', heights=None):
        dur = t1 - t0; ck = hashlib.sha1(json.dumps([self.sig, sid, round(t0, 3), round(t1, 3), frame, fov, follow, cands, prefer, hint, drift, fovs, rs, heights, fixed], sort_keys=True, default=str).encode()).hexdigest()[:16]
        if fixed is None and ck in self.cache:
            cm = self.cache[ck]['cm']; s = dict(id=sid, stage=world, dur=round(dur, 4), camera=cm, shake=shake, env=dict(env or {}), _t0=t0, _t1=t1)
            if frame is not None: s['frame'] = dict(frame)
            if why: s['_why'] = why
            self.shots.append(s); return s
        if fixed is not None:                                        # a camera written by hand: ((pos0, look0), (pos1, look1)) , fov
            (p0, l0), (p1, l1) = fixed; cm = cam(_k(0, p0, l0, fov), _k(dur, p1, l1, fov))
        else:
            fr = dict(frame)
            if hint: fr['from'] = hint
            if follow and cands: mx0, mz0 = self.C.xz(follow, (t0 + t1) / 2); cands = [(mx0 + dx, mz0 + dz) for dx, dz in cands]          # offsets from the followed actor
            kw = dict(prefer=prefer, cands=cands, follow=follow)
            if fovs: fr['fovs'] = fovs
            if rs: kw['rs'] = rs
            if heights: kw['heights'] = heights
            try: sol = CP.solve(self.geo, self.C, fr, t0, t1, ASPECT, fov, **kw)
            except BLK.PlanError as e: self.fail.append(f"plan {sid} [{t0:.1f}-{t1:.1f}] : {e}"); return None
            f_ = sol['fov']
            if follow:
                keys = []; n = max(2, int(dur / .5) + 1); off = sol['offset']
                mx, mz = self.C.xz(follow, (t0 + t1) / 2); ax, az = sol['look'][0] - mx, sol['look'][2] - mz
                for i in range(n + 1):
                    tt = min(dur, i * dur / n); fx, fz = self.C.xz(follow, t0 + tt)
                    keys.append(_k(tt, (fx + off[0], sol['pos'][1], fz + off[1]), (fx + ax, sol['look'][1], fz + az), f_))
                cm = cam(*keys)
            else:
                p, l = sol['pos'], sol['look']
                if drift:
                    d = [l[j] - p[j] for j in range(3)]; n = math.sqrt(sum(v * v for v in d)) or 1.; p1 = [p[j] + d[j] / n * drift for j in range(3)]
                    cm = cam(_k(0, p, l, f_), _k(dur, p1, l, f_))
                else: cm = cam(_k(0, p, l, f_), _k(dur, p, l, f_))
            fov = f_
        s = dict(id=sid, stage=world, dur=round(dur, 4), camera=cm, shake=shake, env=dict(env or {}), _t0=t0, _t1=t1)
        if frame is not None: s['frame'] = dict(frame)
        if why: s['_why'] = why
        if fixed is None: self.cache[ck] = dict(cm=cm); self.cfile.write_text(json.dumps(self.cache, default=str), encoding='utf-8')
        self.shots.append(s); return s


def lift_table(F):
    return astro_env(F)['lift']


def lift_y(tab, t):
    if t <= tab[0][0]: return tab[0][1]
    for i in range(len(tab) - 1):
        if t < tab[i + 1][0]: k = (t - tab[i][0]) / (tab[i + 1][0] - tab[i][0]); return tab[i][1] + (tab[i + 1][1] - tab[i][1]) * k
    return tab[-1][1]


def ship_cam(add, F, sid, t0, t1, off, look_off, fov):
    """a camera that rises with the shuttle (written from the lift table of the world): the ship stays in the frame while the city shrinks below"""
    tab = lift_table(F); n = max(2, int((t1 - t0) / .4)); keys = []
    for i in range(n + 1):
        tt = (t1 - t0) * i / n; y = lift_y(tab, t0 + tt)
        keys.append(_k(tt, (a_(off[0]), y + off[1], off[2]), (a_(look_off[0]), y + 2.2 + look_off[1], look_off[2]), fov))
    s = dict(id=sid, stage='astroport', dur=round(t1 - t0, 4), camera=cam(*keys), shake=.05, env={}, _t0=t0, _t1=t1, _why='rising with the shuttle'); add.__self__.shots.append(s)


def cuts_plan(F, C, geo):
    """the whole film's shot list: (see the comment of each shot for its dramatic reason)"""
    A = F.notes; L = F.talk; hero = {k: v for k, v in C.plan['actors'].items() if v.get('role') != 'extra'}; Z = Cams(geo, C, hashlib.sha1(json.dumps([hero, [b for b in C.plan['beats'] if b['who'] in hero]], sort_keys=True, default=str).encode()).hexdigest()[:12]); add = Z.add; tR = A['end_city']
    t_steal, t_shout = A['steal'], A['shout']; shout_end = L['l05'][1]
    t_in = t_steal + 2.9
    add('S01', 0., 3.4, 'cite', fixed=(((c(20.), 5.6, 4.6), (c(-6.), 2.4, -4.5)), ((c(12.), 4.4, 4.2), (c(-6.), 2.4, -4.5))), fov=68., why='establishing: the street, the café, the crowd, the clock tower')
    add('S02', 3.4, 6.0, 'cite', frame=dict(actors=['ines'], kind='full'), follow='ines', cands=[(5.2, .5), (5.2, -.5), (-5.6, .4), (6.5, 0.)], fov=60., why='she runs through the crowd')
    add('S03', 6.0, L['l01'][0] + .2, 'cite', frame=dict(actors=['ines', 'malo'], kind='medium'), fov=62., why='she arrives, Malo turns')
    add('S04', L['l01'][0] + .2, L['l01'][1] + .15, 'cite', frame=dict(actors=['ines'], kind='close', face=['ines'], context=True), fov=58., why='l01 Inès')
    add('S05', L['l01'][1] + .15, L['l02'][1] + .1, 'cite', frame=dict(actors=['malo'], kind='close', face=['malo'], context=True), fov=58., why='l02 Malo')
    add('S06', L['l02'][1] + .1, A['place'] + 1.5, 'cite', frame=dict(actors=['ines', 'malo'], kind='medium', points=[(c(-3.3), 1.3, -3.1)]), fov=62., why='l03, she puts the case on the table')
    add('S07', A['place'] + 1.5, L['l04'][0] + .5, 'cite', frame=dict(points=[(c(-3.3), 1.3, -3.1)], kind='insert'), fov=46., why='detail: the glowing case on the table')
    add('S08', L['l04'][0] + .5, t_steal - .5, 'cite', frame=dict(actors=['malo', 'vorn'], kind='medium'), fov=62., why='l04, Vorn closes in behind them')
    add('S09', t_steal - .5, t_steal + 2.9, 'cite', frame=dict(actors=['vorn', 'ines'], kind='medium'), fov=64., why='the theft, Vorn runs off, she shouts (l05)')
    add('S10', t_steal + 2.9, L['l06'][1] + .15, 'cite', frame=dict(actors=['ines', 'malo'], kind='medium'), fov=62., why='l06: they see him go into the café')
    add('S12', L['l06'][1] + .15, A['rattle'] - .6, 'cite', fixed=(((c(6.9), 1.9, -14.0), (c(.5), 1.4, -10.0)), ((c(6.9), 1.9, -14.0), (c(-5.5), 1.4, -12.0))), fov=80., frame=dict(actors=['vorn'], kind='wide'), why='inside: Vorn crosses the room to the back door')
    add('S13', A['rattle'] - .6, A['cab_put'] - .3, 'cite', frame=dict(actors=['vorn'], kind='medium', face=['vorn']), fov=60., why='the back door is locked')
    add('S14', A['cab_put'] - .3, L['l07'][0] + .2, 'cite', frame=dict(actors=['vorn'], kind='medium', points=[P_CAB_PT()]), fov=62., why='he puts the case down to free his hands')
    add('S15', L['l07'][0] + .2, L['l07'][1] + .1, 'cite', frame=dict(actors=['vorn'], kind='close', face=['vorn'], context=True), fov=58., why='l07 Vorn')
    add('S16', L['l07'][1] + .1, L['l08'][1] + .3, 'cite', frame=dict(actors=['ines'], kind='close', face=['ines'], context=True), fov=58., why='l08 Inès')
    tf, td = A['jab'], A['draw'] - .5
    add('S17', L['l08'][1] + .3, td + .1, 'cite', fixed=(((c(-6.9), 1.95, -7.1), (c(-5.6), 1.35, -10.9)), ((c(-6.6), 1.95, -7.1), (c(-5.5), 1.35, -10.9))), fov=62., frame=dict(actors=['ines', 'vorn'], kind='wide'), why='the fist fight: master shot, in profile')
    add('S18', td + .1, td + 2.6, 'cite', fixed=(((c(-5.5), 2.0, -7.3), (c(-5.5), 1.35, -10.9)), ((c(-4.9), 2.0, -7.3), (c(-4.5), 1.35, -10.9))), fov=72., frame=dict(actors=['ines', 'vorn'], kind='medium'), why='he draws, she backs off')
    t_take = A['take_sword']
    add('S19', td + 2.6, t_take - .2, 'cite', fixed=(((c(7.3), 3.4, -6.4), (c(-1.0), 1.2, -10.0)), ((c(7.3), 3.4, -6.4), (c(-4.5), 1.2, -12.0))), fov=72., frame=dict(actors=['malo'], kind='wide'), why='Malo runs for the rack')
    add('S20', t_take - .2, A['catch'] + .2, 'cite', frame=dict(actors=['malo', 'ines'], kind='wide'), fov=68., hint=dict(at=[c(-3.0), -8.0], r=3.2), why='he throws, she catches')
    add('S21', A['catch'] + .2, A['clash2'] + .35, 'cite', fixed=(((c(-2.0), 2.2, -7.3), (c(-4.0), 1.35, -10.9)), ((c(-2.0), 2.2, -7.3), (c(-4.1), 1.35, -10.9))), fov=60., frame=dict(actors=['ines', 'vorn'], kind='medium'), why='two blades')
    add('S22', A['clash2'] + .35, A['thrust'] + .3, 'cite', fixed=(((c(-2.2), 2.0, -7.5), (c(-4.0), 1.35, -10.9)), ((c(-2.8), 1.9, -7.8), (c(-4.0), 1.4, -10.9))), fov=56., frame=dict(actors=['ines', 'vorn'], kind='medium'), why='she disarms him, the point at his throat')
    add('S23', A['thrust'] + .3, L['l11'][1] + .2, 'cite', frame=dict(actors=['ines'], kind='close', face=['ines'], context=True), cands=[(c(-5.2), -8.4), (c(-4.6), -8.0), (c(-5.8), -8.8), (c(-5.6), -7.9)], heights=(1.55, 1.7, 1.45), fov=54., why='l11 Inès, in profile above the fallen blade')
    t_flee = L['l11'][1] + .35
    add('S24', L['l11'][1] + .2, A['cab_take'] - 1.2, 'cite', frame=dict(actors=['vorn'], kind='wide'), follow='vorn', cands=[(0., 4.5), (-3., 3.), (3., 3.), (-5., 0.)], fov=62., why='Vorn flees')
    add('S25', A['cab_take'] - 1.2, A['out'] + .2, 'cite', frame=dict(actors=['ines'], kind='medium'), fov=62., hint=dict(at=[c(-3.0), -8.0], r=3.5), why='she takes the case back; l12')
    t_o1 = A['out'] + 3.9
    add('S26', A['out'] + .2, t_o1, 'cite', frame=dict(actors=['ines', 'malo'], kind='wide'), fov=66., hint=dict(at=[c(3.), 0.5], r=5.), why='out of the café')
    add('S27', t_o1, A['out'] + 8.3, 'cite', fixed=(((c(12.), 2.6, 6.9), (c(2.), 1.4, -4.0)), ((c(12.), 2.6, 6.9), (c(-8.), 1.4, -4.2))), fov=74., frame=dict(actors=['ines'], kind='wide'), why='running west along the pavement')
    add('S28', A['out'] + 8.3, tR, 'cite', fixed=(((c(-9.2), 1.8, -.8), (c(-9.2), 1.5, -30.)), ((c(-9.2), 1.8, -.8), (c(-9.2), 1.5, -34.))), fov=68., frame=dict(actors=['ines', 'malo'], kind='wide', show=['monte_charge']), why='down the alley to the freight lift, the doors close')
    # ---- the roof
    add('S29', tR, L['l13'][1] + .15, 'astroport', fixed=(((a_(-19.4), 1.62, -.25), (a_(-21.0), 1.6, .85)), ((a_(-19.4), 1.62, -.25), (a_(-21.0), 1.6, .85))), fov=64., frame=dict(actors=['ines_r'], kind='close', face=['ines_r'], context=True), why='l13 in the lift cab')
    add('S30', L['l13'][1] + .15, A['roof_open'] + .6, 'astroport', fixed=(((a_(-19.4), 1.62, .25), (a_(-21.0), 1.6, -.85)), ((a_(-19.4), 1.62, .25), (a_(-21.0), 1.6, -.85))), fov=64., frame=dict(actors=['malo_r'], kind='close', face=['malo_r'], context=True), why='l14')
    t_e1 = A['roof_open'] + 3.4
    add('S32', A['roof_open'] + .6, A['ramp'], 'astroport', fixed=(((a_(6.), 5.5, -12.6), (a_(-19.), 1.2, 0.5)), ((a_(6.), 5.5, -12.6), (a_(3.5), 1.2, -4.5))), fov=74., frame=dict(actors=['ines_r'], kind='wide'), why='the doors open, they run round the nose of the shuttle to the ramp')
    add('S33', A['ramp'], A['board'], 'astroport', fixed=(((a_(6.5), 1.7, -6.0), (a_(4.5), 1.5, -2.6)), ((a_(6.5), 1.7, -6.0), (a_(4.5), 1.5, -2.6))), fov=60., frame=dict(actors=['ines_r', 'malo_r'], kind='medium'), why='at the foot of the ramp')
    L0 = A['launch']; b0 = A['board']
    add('S34', A['board'], L0 + .4, 'astroport', fixed=(((a_(13.), 2.4, 9.5), (a_(0.), 2.3, -1.)), ((a_(12.), 2.2, 9.), (a_(0.), 2.3, -1.))), fov=62., why='the hatch closes, the engines wake up (they have boarded: cut)')
    add('S35', L0 + .4, L0 + 4.0, 'astroport', fixed=(((a_(7.), .8, 6.), (a_(0.), 3., -1.)), ((a_(7.), .8, 6.), (a_(0.), 14., -1.))), fov=66., why='low angle: the shuttle lifts off')
    ship_cam(add, F, 'S36', L0 + 4.0, L0 + 8.6, (28., 16., 26.), (0., -3., -1.), 62.)
    ship_cam(add, F, 'S37', L0 + 8.6, A['end_roof'], (30., 30., 40.), (0., 0., -1.), 60.)
    # ---- the Moon
    tM = A['moon']; ts = A['moon_stand']
    add('S38', tM, tM + 3.0, 'selene', fixed=(((s_(-1.), 1.5, 10.), (s_(-8.), 2.6, 1.)), ((s_(-3.), 1.7, 9.), (s_(-8.), 2.6, 1.))), fov=64., why='the Moon: the landed shuttle, the two small figures')
    add('S39', tM + 3.0, ts, 'selene', frame=dict(actors=['ines_m'], kind='wide'), follow='ines_m', cands=[(0., 5.), (3., 4.), (-3., 4.)], fov=62., why='they walk to the dead beacon')
    add('S40', ts, A['insert'] - .3, 'selene', frame=dict(actors=['ines_m', 'malo_m'], kind='medium'), fov=62., hint=dict(at=[s_(7.5), 6.], r=3.), why='l16, the console')
    add('S41', A['insert'] - .3, A['beacon_on'] + .1, 'selene', fixed=(((s_(6.0), 1.6, 3.4), (s_(8.0), 1.3, .9)), ((s_(6.4), 1.55, 3.0), (s_(8.0), 1.3, .9))), fov=52., frame=dict(actors=['ines_m'], kind='medium'), why='she slides the core in')
    add('S42', A['beacon_on'] + .1, A['beacon_on'] + 2.6, 'selene', fixed=(((s_(3.), 1.0, 7.), (s_(8.), 5., -1.)), ((s_(3.), 1.0, 7.), (s_(8.), 14., -1.))), fov=68., why='the beacon lights up')
    add('S43', A['beacon_on'] + 2.6, A['end_moon'], 'selene', frame=dict(actors=['ines_m', 'malo_m'], kind='medium'), fov=62., hint=dict(at=[s_(6.5), 5.], r=3.), why='l18, the Earth lights up')
    # ---- the city, at night, lit again
    cn = A['city_night']
    if Z.fail: raise BLK.PlanError(chr(99)+'améras impossibles :' + chr(10) + '  ' + (chr(10) + '  ').join(Z.fail))
    add('S44', cn, A['end'], 'cite', fixed=(((c(20.), 4.2, 9.0), (c(2.), 3.0, -4.)), ((c(12.), 8.6, 8.4), (c(2.), 4.5, -4.))), fov=64., env=dict(), why='the city lights up: the payoff')
    return Z


def P_CAB_PT(): return (c(-7.1), 1.3, -11.1)


# ------------------------------------------------------------------------------------------------------------------ sound
def sound_of(F, C):
    A = F.notes; S_ = []; add = lambda t, n, g=.8, dur=None: S_.append(dict(t=round(t, 3), name=n, gain=g, dur=dur))
    for e in C.events:
        if e['kind'] == 'strike':
            if e['weapon']:
                add(e['t'] - .13, 'whoosh', .5)
                if e['hit']: add(e['t'], 'metal_hit', .8)
            else:
                add(e['t'] - .08, 'whoosh', .35)
                add(e['t'], 'punch' if e['hit'] else 'cloth', .9 if e['hit'] else .5)
        elif e['kind'] == 'clash': add(e['t'], 'sword_clash', .85)
        elif e['kind'] == 'draw': add(e['t'] + .25, 'metal_hit', .45)
    add(A['steal'], 'cloth', .5); add(A['steal'] + .1, 'pickup', .6); add(A['place'], 'thump', .5); add(A['rattle'], 'lock_rattle', .8); add(A['rattle'] + .7, 'door_handle', .5)
    add(A['cab_put'], 'thump', .5); add(A['throw'], 'whoosh', .6); add(A['catch'], 'pickup', .7); add(A['disarm'] + .35, 'metal_hit', .6); add(A['disarm'] + .75, 'thump', .5)
    add(A['take_sword'], 'metal_hit', .4)
    for (a, b) in (F.ev['door1'], F.ev['door2'], F.ev['door3']): add(a, 'door_open', .5); add(b, 'door_slam', .6)
    add(F.ev['lift_open'][0] + .3, 'elevator_ding', .7); add(F.ev['lift_open'][1] - .5, 'door_slam', .5); add(A['end_city'] - .2, 'elevator_motor', .5, 6.)
    add(A['roof_open'] - .3, 'elevator_ding', .7); add(A['roof_open'], 'door_open', .5)
    add(A['launch'] + 11.9 - 11.9, 'church_bell', .8, 5.); add(A['board'], 'door_slam', .5)
    add(A['launch'] - .8, 'riser', .6, 4.); add(A['launch'], 'engine', .9, 10.); add(A['launch'] + .3, 'boom', .7); add(A['launch'] + 1, 'fire_whoosh', .6, 6.)
    add(A['insert'], 'click', .7); add(A['insert'] + .4, 'success', .7); add(A['beacon_on'], 'riser', .5, 2.); add(A['beacon_on'] + 1.3, 'magic', .6)
    add(A['shout'] + .2, 'crowd', .5, 3.)
    return sorted(S_, key=lambda e: e['t'])


def audio_of(F, C, voice_wav):
    A = F.notes; E = A['end']; seg = lambda t0, t1, st, g, fade=1.5: dict(t0=t0, t1=t1, style=st, gain=g, seed=0, fade=fade)
    return dict(music=[seg(0, A['steal'] - 1., 'adventure', .30), seg(A['steal'] - 1., A['out'] + .5, 'action', .34), seg(A['out'] + .5, A['end_city'] + 8., 'adventure', .30), seg(A['end_city'] + 6., A['moon'] + 1, 'epic', .36, 2.),
                       seg(A['moon'], A['beacon_on'] + .5, 'calm', .26, 2.), seg(A['beacon_on'] - .2, E + .5, 'epic', .34, 1.5)],
                ambience=[dict(t0=0, t1=A['steal'] + 2., name='city', gain=.30), dict(t0=0, t1=A['steal'] + 2., name='crowd', gain=.14), dict(t0=A['steal'], t1=A['out'], name='cafe', gain=.22), dict(t0=A['out'], t1=A['end_city'] + 1., name='city', gain=.25),
                          dict(t0=A['end_city'], t1=A['launch'] + 5., name='wind', gain=.22), dict(t0=A['moon'] - .5, t1=A['beacon_on'] + 2, name='space', gain=.45), dict(t0=A['city_night'], t1=E + .5, name='city', gain=.2), dict(t0=A['city_night'], t1=E + .5, name='night', gain=.14)],
                sfx=sound_of(F, C), foley=dict(steps=True, gain=.5), voice=dict(wav=str(voice_wav), gain=1.0, duck=.55))


# ------------------------------------------------------------------------------------------------------------------ the episode
def build(compile_only=False):
    V = D.voice(); F = S.story(V)
    rep = LV.assemble(F.placed, F.duration, WORK / 'voice_mix')
    for aid, sp in F.actors.items():
        if sp.get('lipsync'):
            spk = SPEAKER[aid]; sp['lipsync'] = dict(envelope=rep['speakers'][spk]['env'], hz=30., t0=0., gain=1.)
    A = F.notes
    # an ordinary actor never changes place without walking: the two who board the shuttle LEAVE the film at a cut (declared), and Vorn leaves the street the same way
    beats = list(F.beats)
    beats += [dict(who='ines_r', t=round(A['board'], 3), do='vanish', how='cut', why='monte à bord de la navette (coupe)'), dict(who='malo_r', t=round(A['board'], 3), do='vanish', how='cut', why='monte à bord de la navette (coupe)')]
    plan = dict(actors=F.actors, beats=beats, duration=F.duration, react='auto')
    ep = dict(title='Le Dernier Noyau', genre='adventure', aspect=ASPECT, fps=FPS, duration=F.duration, mood='neutral', casts=casts_of(F), shots=[], world_env=None, captions=F.captions, caption_style=dict(y=.80, size=.04),
              blocking=dict(world='demo', doors=doors(F), plan=plan, world_keys=[], audit='strict', tight_max=.45, insert_max=4), faces=True, face_model='human')
    ep['world_env'] = {**world_env(F), **astro_env(F), **selene_env(F)}
    ep['gait'] = 'planted'                                        # the opt-in planted gait (footkin.planted_gait): the stride plants the foot; measured in tools/demo_cite_audit.py
    E = F.duration; fx = [dict(type='fade', t0=0., t1=.8, **{'from': 0., 'to': 1.}), dict(type='fade', t0=E - 1.4, t1=E, **{'from': 1., 'to': 0.})]
    for e in [b for b in beats if b['do'] in ('strike', 'clash')]:
        pass
    sh = lambda t, a, d=.3: fx.append(dict(type='shake', t0=round(t - .05, 3), t1=round(t + d, 3), amount=a))
    sh(A['punch_hit'], .35); sh(A['clash1'], .3); sh(A['clash2'], .3); sh(A['disarm'], .4); sh(A['steal'] + .2, .15); sh(A['rattle'], .2); sh(A['catch'], .2)
    fx.append(dict(type='shake', t0=round(A['launch'] - .3, 3), t1=round(A['launch'] + 4.5, 3), amount=.45)); fx.append(dict(type='flash', t0=round(A['beacon_on'] + .9, 3), t1=round(A['beacon_on'] + 1.7, 3), **{'from': 1., 'to': 0.}, peak=.55, color='#bfe8ff'))
    ep['fx'] = fx
    ep['blocking']['plan']['face'] = {'model': 'human'}
    return V, F, ep


def episode(with_cameras=True):
    V, F, ep = build()
    if not with_cameras: return ep, F
    geo = stagegeo.GEOS['demo'](ep['blocking']['doors']); from .. import genre_intent as G
    plan2, vs, lives = G.split_plan(dict(ep['blocking']['plan'], duration=ep['duration']))
    C = BLK.compile_plan(plan2, geo)
    import hashlib; key = hashlib.sha1(json.dumps([plan2, cuts_plan.__code__.co_code.hex()], sort_keys=True, default=str).encode()).hexdigest()[:16]; cache = WORK / 'cameras_cache.json'
    if cache.exists() and json.loads(cache.read_text(encoding='utf-8')).get('key') == key: shots_cached = json.loads(cache.read_text(encoding='utf-8'))['shots']
    else:
        shots_cached = sorted(cuts_plan(F, C, geo).shots, key=lambda s: s['_t0']); cache.write_text(json.dumps(dict(key=key, shots=shots_cached), default=str), encoding='utf-8')
    class _Z: pass
    Z = _Z(); Z.shots = shots_cached
    shots = sorted(Z.shots, key=lambda s: s['_t0']); gaps = []
    for i, s in enumerate(shots):                                   # the shots tile the film: a gap or an overlap smaller than 0.7 s is absorbed by the previous shot (and written down), a larger one is an error
        nxt = shots[i + 1]['_t0'] if i + 1 < len(shots) else ep['duration']
        if abs(nxt - s['_t1']) > 1e-4:
            if abs(nxt - s['_t1']) > .7: raise BLK.PlanError(f"plans {s['id']} -> suivant : trou ou chevauchement de {nxt - s['_t1']:.2f} s")
            gaps.append((s['id'], round(nxt - s['_t1'], 3))); s['dur'] = round(nxt - s['_t0'], 4)
    ep['_shot_gaps_absorbed'] = gaps
    P = props_of(F); Lg = lights_of(F)
    for s in shots:
        s['props'] = P.get(s['stage'], []); s['lights'] = Lg.get(s['stage'], [])
    ep['shots'] = shots
    wav = WORK / 'voice_mix' / 'voice.wav'; ep['audio'] = audio_of(F, C, wav)
    return ep, F
