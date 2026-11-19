"""The blocking of « Le Dernier Noyau » (see demo_cite.py for the story): every actor of the film, in absolute time, from the dialogue durations.
`story(V)` -> a `Film` (beats, props, sounds, notes = named instants the cameras and the sound read)."""
import math
from . import demo_cite as D
from . import demo_cite_cast as CAST
from .demo_cite import Film, c, a_, s_, PI

P_CASE = (c(-3.38), 1.28, -3.28)             # the case on the tall terrace table, its handle at the north-west corner
P_CAB = (c(-7.05), 1.27, -11.1)              # the case on the cabinet by the back door
VB = (c(-5.9), -10.9)                        # where Vorn fights, facing east; Inès faces him from the east side
IB = (c(-5.25), -10.9)


def crowd(F, T_end):
    """the living street: pedestrians on fixed lanes, a market, café regulars, terrace guests. Everyone belongs to the city world."""
    ids = []
    def ped(i, lane, xa, xb, v, ph, stops=()):
        aid = f'p{i:02d}'; st, bt = CAST.pedestrian(aid, lane, c(xa), c(xb), v, ph, T_end, stops); F.actor(aid, st, vmax=3.8, role='extra', idx=i); F.beats.extend(bt); ids.append(aid)
    ped(1, -4.9, -44, -13.5, 1.10, .15, ((1, 3.0),)); ped(2, -2.4, -43, -13.0, 1.25, .75); ped(3, -4.6, 14, 44, 1.15, .30, ((1, 2.5),)); ped(4, -3.2, 13, 42, 1.20, .80)
    ped(5, 7.05, -14, 18, 1.20, .10); ped(6, 7.9, -13, 20, 1.10, .60, ((2, 2.0),)); ped(7, 7.05, 30, 50, 1.20, .40); ped(8, 7.9, 30, 52, 1.00, .90)
    def stand(i, at, yaw, looks=(), emotes=()):
        aid = f'p{i:02d}'; st, bt = CAST.bystander(aid, at, yaw, T_end, looks, emotes); F.actor(aid, st, vmax=3.8, role='extra', idx=i); F.beats.extend(bt); ids.append(aid); return aid
    for i, x in ((9, -30.0), (10, -26.6), (11, -19.8)): stand(i, (c(x), 9.0), PI, looks=((6. + i, [c(x), 6.0]), (10. + i, None)), emotes=((8., 'smile'),))     # vendors
    stand(12, (c(-30.0), 6.9), 0., looks=((5., [c(-30.0), 8.0]),)); stand(13, (c(-23.2), 6.9), 0., looks=((9., [c(-23.2), 8.0]),))                                              # customers
    for i, x in ((14, -1.35), (15, -.2), (16, .95)): stand(i, (c(x), -11.85), 0., looks=((3. + i % 3, [c(x), -13.4]),))                                                     # café regulars at the bar
    stand(17, (c(-2.4), -14.45), 0.)                                                                                                                                         # barista
    stand(23, (c(10.0), -4.5), PI / 2, looks=((7., [c(11.2), -3.6]),)); stand(24, (c(11.2), -3.5), -PI / 2, emotes=((8., 'happy'),))                      # pairs chatting on the pavement
    stand(31, (c(-8.0), 8.9), PI, looks=((6., [c(-6.8), 8.9]),), emotes=((9., 'smile'),)); stand(32, (c(-6.8), 8.9), PI, looks=((5., [c(-8.0), 8.9]),))        # two friends talking in front of the hotel
    stand(33, (c(2.0), 8.9), 0., looks=((7., [c(3.3), 8.9]),)); stand(34, (c(3.3), 8.9), 0.); stand(35, (c(11.5), 8.9), 0., looks=((10., [c(11.5), 6.0]),))             # reading the menu of the crêperie, a man waiting
    stand(18, (c(.8), -3.5), -PI / 2, looks=((4., [c(-0.2), -3.5]),)); stand(19, (c(1.4), -2.4), PI / 2); stand(20, (c(3.55), -2.9), -PI / 2)                                    # terrace guests
    # the regulars back away from the fight, the barista ducks behind the bar, the terrace guests look at the shout and at the door
    T = F.notes
    for k_, (aid, to) in enumerate((('p16', (c(6.9), -10.6)), ('p15', (c(6.6), -13.1)), ('p14', (c(4.4), -13.7)))): F.walk(aid, T['fight_in'] + .1 + k_ * .7, list(to), v=2.4, face=[c(-5.5), -10.9])
    F.beat('p17', T['fight_in'] + .4, 'kneel', until=T['sword_down'] + .5, amount=.85)
    for aid in ('p14', 'p15', 'p16', 'p17'): F.beat(aid, T['fight_in'] + .2, 'emote', face='scared')
    return ids


def rest(F, V):
    """the roof, the Moon and the crowd (beats), after the city part"""
    B = F.beat; go = F.go; say = F.say; A = F.notes
    tR = A['end_city']                                                  # hard cut to the roof: the lift cab, then the pad
    F.actor('ines_r', dict(at=[a_(-21.0), .85], yaw=PI), vmax=5.2, lipsync=True); F.actor('malo_r', dict(at=[a_(-21.0), -.85], yaw=0.), vmax=5.2, lipsync=True)
    B('malo_r', tR + .2, 'emote', face='worried'); B('ines_r', tR + .2, 'emote', face='determined')
    t13 = say('l13', tR + .9); t14s = t13 + .35; t14 = say('l14', t14s); B('malo_r', t14s, 'emote', face='determined')
    t_open = t14 + .5; A['roof_open'] = t_open; F.ev['lift_roof'] = (t_open, t_open + 40.)
    t_e1 = F.walk('ines_r', t_open + .5, [a_(-14.0), -3.3], v=4.4); t_e2 = F.walk('ines_r', t_e1 + .05, list((a_(4.6), -3.35)), v=4.6, face=[a_(1.0), -2.6])
    m_e1 = F.walk('malo_r', t_open + .75, [a_(-14.0), -1.6], v=4.4); m_e2 = F.walk('malo_r', m_e1 + .05, [a_(4.6), -1.8], v=4.6, face=[a_(1.0), -2.6])
    t_arrive = max(t_e2, m_e2); A['ramp'] = t_arrive
    B('ines_r', t_arrive + .1, 'emote', face='determined'); B('malo_r', t_arrive + .1, 'look', at=[a_(0.), 2.0, 2.0] if False else [a_(0.), 0.]); B('ines_r', t_arrive + .5, 'look', at=[a_(0.), 0.])
    t_board = t_arrive + 1.1; A['board'] = t_board
    F.board = [('ines_r', t_board), ('malo_r', t_board + .1)]
    t_launch = t_board + 1.2; A['launch'] = t_launch; A['end_roof'] = t_launch + 11.5       # the ascent: 11.5 s of shuttle, sky and city
    # ---------------------------------------------------------------------------------------------- the Moon
    tM = A['end_roof'] + .3; A['moon'] = tM
    F.actor('ines_m', dict(at=[s_(-5.5), 4.5], yaw=PI), vmax=5.2, lipsync=True); F.actor('malo_m', dict(at=[s_(-6.9), 5.7], yaw=PI), vmax=5.2, lipsync=True)
    t15 = say('l15', tM + 1.6)
    a1 = F.walk('ines_m', tM + 1.2, [s_(8.38), 1.4], v=2.7, face=[s_(8.38), -1.0]); a2 = F.walk('malo_m', tM + 1.6, [s_(6.9), 1.8], v=2.8, face=[s_(8.0), -1.0])
    t_stand = max(a1, a2) + .2; A['moon_stand'] = t_stand
    t16 = say('l16', t_stand + .4); B('malo_m', t_stand + .4, 'emote', face='determined')
    t_ins = t16 + .5; B('ines_m', t_ins, 'touch', target=[s_(8.0), 1.22, .95], hand='L', pose='grip', dur=.8); A['insert'] = t_ins + .35
    t17 = say('l17', t_ins + .15); B('ines_m', t_ins, 'emote', face='determined')
    A['beacon_on'] = t_ins + 1.3
    t18s = A['beacon_on'] + 1.8; t18 = say('l18', t18s); B('malo_m', t18s - .6, 'look', at=[s_(-25.), -90., 28.]); B('ines_m', t18s - .3, 'look', at=[s_(-25.), -90., 28.])
    B('ines_m', A['beacon_on'] + .2, 'emote', face='joy'); B('malo_m', A['beacon_on'] + .5, 'emote', face='joy')
    A['end_moon'] = t18 + 1.6
    A['city_night'] = A['end_moon'] + .2; A['end'] = A['city_night'] + 7.5
    F.duration = A['end']
    crowd(F, A['end'] + 1.)
    # the city looks up when the lights come back
    for aid in [k for k, v in F.actors.items() if v.get('role') == 'extra']:
        if aid in ('p01', 'p02', 'p03', 'p04', 'p05', 'p06', 'p07', 'p08'): continue
        B(aid, A['city_night'] + 2.0, 'look', at=[c(14.0), -9.0, 25.0]); B(aid, A['city_night'] + 2.2, 'emote', face='joy')
    for aid in ('ines_r', 'malo_r', 'ines_m', 'malo_m'): F.actors[aid]['worlds'] = ['astroport' if aid.endswith('_r') else 'selene']
    for aid, v in F.actors.items():
        if 'worlds' not in v: v['worlds'] = ['cite']


def story(V):
    F = Film(V); B = F.beat; say = F.say; go = F.go; A = F.notes
    # ---------------------------------------------------------------------------------------------- the heroes (city)
    F.actor('ines', dict(at=[c(-27.0), -3.65], yaw=PI / 2), vmax=5.2, lipsync=True)
    F.actor('malo', dict(at=[c(-4.95), -4.45], yaw=-PI / 2), vmax=5.2, lipsync=True)
    F.actor('vorn', dict(at=[c(2.4), -4.95], yaw=-PI / 2), vmax=5.8, lipsync=True)
    # ---------------------------------------------------------------------------------------------- scene 1 : she runs in (0 - 8)
    go('ines', 1.0, [c(-3.85), -3.65], 7.4, face='malo')
    B('malo', 3.2, 'look', at='ines'); B('malo', 5.8, 'emote', face='happy')
    B('vorn', 2.0, 'look', at='ines')
    # ---------------------------------------------------------------------------------------------- scene 2 : the terrace
    t = 7.8
    t1 = say('l01', t); B('ines', t, 'emote', face='joy')
    t2s = t1 + .30; t2 = say('l02', t2s); B('malo', t2s, 'emote', face='relief')
    t3s = t2 + .25; t3 = say('l03', t3s); B('ines', t3s, 'emote', face='determined')
    t_place = t3s + .55
    B('ines', t_place - 1.1, 'face', at=[c(-1.0), -3.65]); B('ines', t_place, 'touch', target=list(P_CASE), hand='R', pose='open', dur=.7); B('ines', t_place + 1.4, 'face', at='malo')
    A['place'] = t_place + .25
    t4s = t3 + .25; t4 = say('l04', t4s); B('malo', t4s, 'emote', face='worried')
    t_steal = t4s + 1.35
    go('vorn', t3s + .6, [c(-3.0), -3.72], t_steal - .45, face=[c(-3.0), -2.0])
    b_vcase = B('vorn', t_steal, 'take', target=list(P_CASE), hand='R', pose='grip', item='mallette', until=t_steal + 12.)
    B('vorn', t_steal + .1, 'emote', face='grin'); A['steal'] = t_steal
    B('malo', t_steal + .25, 'look', at='vorn'); B('malo', t_steal + .3, 'emote', face='shocked')
    B('ines', t_steal + .35, 'face', at='vorn'); B('ines', t_steal + .3, 'emote', face='furious')
    t5s = t_steal + .55; t5 = say('l05', t5s, event='scream'); A['shout'] = t5s
    # ---------------------------------------------------------------------------------------------- scene 3 : the chase (the terrace, the café)
    door1 = (t_steal + 1.2, t_steal + 6.4)
    go('vorn', t_steal + .5, [c(4.6), -7.15], t_steal + 2.7, face=[c(4.6), -9.0])
    t_back = t_steal + 6.4
    go('vorn', t_steal + 2.75, [c(-7.52), -12.77], t_back, face=[c(-9.0), -12.77])
    B('vorn', t_back + .6, 'touch', target=[c(-7.8), 1.1, -13.0], hand='R', pose='fist', dur=.55); A['rattle'] = t_back + .75
    go('ines', t5s + .85, [c(4.6), -7.15], t5s + 3.4, face=[c(4.6), -9.0])
    t6s = t5 + .15; t6 = say('l06', t6s)
    go('malo', t5s + 1.5, [c(3.3), -6.9], t5s + 4.3)
    t_cab = t_back + 1.6
    go('vorn', t_back + 1.5, [c(-6.72), -10.72], t_cab + 1.5, face=[c(-9.0), -10.72])
    t_cabtouch = t_cab + 1.05
    B('vorn', t_cabtouch, 'touch', target=list(P_CAB), hand='R', pose='open', dur=.55); A['cab_put'] = t_cabtouch + .2; b_vcase['until'] = t_cabtouch + .2
    t_arr = t_cab + 1.35
    go('ines', t5s + 3.5, [IB[0], IB[1]], t_arr + 1.4, face='vorn')
    B('malo', t_arr + .6, 'look', at='vorn')
    t7s = t_cabtouch + .9; A['fight_in'] = t7s; t7 = say('l07', t7s); B('vorn', t7s, 'emote', face='angry')
    go('vorn', t7s + .1, list(VB), t7s + 1.0, face='ines')
    t8s = t7 + .2; t8 = say('l08', t8s); B('ines', t8s, 'emote', face='determined')
    # ------------------------------------------------ the fist fight
    tf = t8 + .35
    B('vorn', tf, 'strike', at='ines', hand='R', kind='jab', height='chest', hit=False)
    B('ines', tf - .05, 'guard', until=tf + .5, hand='L', at='vorn')
    B('ines', tf + .55, 'strike', at='vorn', hand='R', kind='cross', height='head', hit=True)
    B('vorn', tf + .58, 'flinch', amount=-.7, dur=.5); B('vorn', tf + .58, 'emote', face='pain')
    go('vorn', tf + .62, [VB[0] - .5, VB[1]], tf + 1.25, backwards=True, face='ines')
    B('ines', tf + 1.2, 'emote', face='determined')
    A['punch_hit'] = tf + .55; A['jab'] = tf
    td = tf + 1.7; t9s = td - .35; t9 = say('l09', t9s)
    B('vorn', td + .5, 'draw', at='ines', hand='L', until=td + 14.0, item='epee'); A['draw'] = td + .5
    B('malo', td + .2, 'emote', face='scared')
    go('malo', td + .1, [c(-5.4), -12.6], td + 2.9)
    go('malo', td + 2.95, [c(-7.28), -14.92], td + 4.3, face=[c(-7.28), -16.5])
    t_take = td + 4.4
    B('malo', t_take, 'take', target='epee_a', hand='R', pose='grip', item='epee', until=t_take + 1.25); A['take_sword'] = t_take
    # the fight retreats east as Vorn advances, about one metre apart at every exchange
    go('ines', td + .9, [c(-4.55), -10.9], td + 1.6, backwards=True, face='vorn')
    go('vorn', td + 1.0, [c(-5.5), -10.9], td + 1.8, face='ines')
    B('vorn', td + 2.0, 'strike', at='ines', hand='L', kind='slash', height='chest', hit=False); A['slash1'] = td + 2.0
    B('ines', td + 1.95, 'guard', until=td + 2.45, hand='L', at='vorn')
    go('ines', td + 2.2, [c(-4.0), -10.9], td + 2.95, backwards=True, face='vorn')
    go('vorn', td + 2.3, [c(-4.95), -10.9], td + 3.05, face='ines')
    B('vorn', td + 3.2, 'strike', at='ines', hand='L', kind='overhead', height='head', hit=False)
    go('ines', td + 3.4, [c(-3.5), -10.9], td + 4.15, backwards=True, face='vorn')
    go('vorn', td + 3.5, [c(-4.4), -10.9], td + 4.25, face='ines')
    B('vorn', td + 4.4, 'strike', at='ines', hand='L', kind='slash', height='chest', hit=False)
    B('ines', td + 4.35, 'guard', until=td + 4.85, hand='L', at='vorn')
    B('vorn', td + 5.3, 'strike', at='ines', hand='L', kind='slash', height='high', hit=False)
    t10s = t_take + .55; t10 = say('l10', t10s)
    B('malo', t_take + .75, 'face', at='ines')
    B('malo', t_take + 1.2, 'aim', at='ines', until=t_take + 1.7, hand='R', reach=.5, h=1.5, pose='open')
    t_throw = t_take + 1.3; t_catch = t_throw + .62; A['throw'] = t_throw; A['catch'] = t_catch
    P_CATCH = (c(-3.9), 1.38, -11.28); A['p_catch'] = P_CATCH
    b_isword = B('ines', t_catch, 'take', target=list(P_CATCH), hand='R', pose='grip', item='epee', until=t_catch + 14.)
    B('ines', t_catch - .3, 'face', at='vorn')
    tc1 = t_catch + .95
    B('vorn', tc1 - .1, 'strike', at='ines', hand='L', kind='slash', height='chest', hit=False)
    B('ines', tc1, 'clash', b='vorn', hand='R', hand_b='L', dur=.55, h=1.45); A['clash1'] = tc1
    tc2 = tc1 + 1.35
    B('ines', tc2, 'clash', b='vorn', hand='R', hand_b='L', dur=.5, h=1.5); A['clash2'] = tc2
    t_dis = tc2 + .95
    B('ines', t_dis, 'strike', at='vorn', hand='R', kind='slash', height='chest', hit=True); A['disarm'] = t_dis
    B('vorn', t_dis + .03, 'flinch', amount=-.5, dur=.4); B('vorn', t_dis + .03, 'emote', face='scared')
    t_thr = t_dis + .75
    B('ines', t_thr, 'strike', at='vorn', hand='R', kind='thrust', height='head', hit=False, dur=.5); A['thrust'] = t_thr
    t11s = t_thr + .5; t11 = say('l11', t11s)
    t_flee = t11 + .35
    go('ines', t_thr + .9, [c(-3.5), -9.4], t_thr + 1.9, face='vorn')
    t_d = F.walk('vorn', t_flee, [c(4.6), -7.15], v=5.0, face=[c(4.6), -4.0]); door2 = (t_d - 1.2, t_d + 2.6)
    F.walk('vorn', t_d + .05, [c(8.6), -2.6], v=4.6)
    t_cabtake = F.walk('ines', t_flee + .4, [c(-6.72), -11.48], v=4.2, face=[c(-9.0), -11.48]) + .1
    B('ines', t_cabtake + .2, 'take', target=list(P_CAB), hand='L', pose='grip', item='mallette', until=1e9); A['cab_take'] = t_cabtake + .2; b_isword['until'] = t_cabtake + 1.0; A['sword_down'] = t_cabtake + 1.0
    t12s = t_cabtake + .75; t12 = say('l12', t12s)
    F.walk('malo', t_flee + .4, [c(4.2), -7.3], v=4.4)
    # ---------------------------------------------------------------------------------------------- scene 4 : out of the café, along the pavement, down the alley, into the lift
    t_out = t12s + .8; A['out'] = t_out
    t_o1 = F.walk('ines', t_out, [c(4.6), -4.3], v=4.4)
    t_o2 = F.walk('ines', t_o1 + .05, [c(-9.6), -4.4], v=4.4)
    t_o3 = F.walk('ines', t_o2 + .05, [c(-9.6), -33.4], v=4.4)
    m1 = F.walk('malo', t_out + .9, [c(4.5), -4.6], v=4.4); door3 = (min(t_o1, m1) - 2.0, max(t_o1, m1) + 1.2); m2 = F.walk('malo', m1 + .05, [c(-8.6), -4.4], v=4.4); m3 = F.walk('malo', m2 + .05, [c(-8.6), -31.6], v=4.4)
    t_lift = max(t_o3, m3) + .3
    lift_open = (t_lift - 1.8, t_lift + 3.4)
    t_l1 = F.walk('ines', t_lift, [c(-9.7), -35.8], v=3.0); F.walk('malo', t_lift + 1.3, [c(-8.7), -35.9], v=3.0)
    A['lift_in'] = t_lift; A['end_city'] = t_l1 + .9
    F.ev = dict(door1=door1, door2=door2, door3=door3, lift_open=lift_open)
    rest(F, V)
    return F
