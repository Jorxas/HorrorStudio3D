"""python tools/sfx_bank_import.py [--dry] [--only oculus|wyzowl|wikimedia]

Construit la bibliothèque de VRAIS sons du moteur VOXEL : `library/audio_real/` (un manifeste au même format que `library/audio/manifest.json`, lu par
`hstudio.audio.library.SoundLibrary(root=...)`). Elle est séparée de la bibliothèque historique pour que les épisodes et les tests existants ne changent pas d'un bit.

Banques (sources locales dans ../assets_externes/sons/, licence lue dans le dépôt avant import) :
  * oculus   : « Oculus Audio Pack 01 » (Oculus VR / Meta), CC BY 4.0 -> CRÉDIT EXIGÉ si une vidéo publiée l'utilise. Vrais enregistrements : pas sur 6 surfaces, portes, grincements, boucles.
  * wyzowl   : « SFX Kit » (Wyzowl), CC0. Sons dessinés (impacts, grondements, whooshes, tonnerre) : `kind: designed`, pas des enregistrements de terrain.
  * wikimedia: les 7 enregistrements CC0 / domaine public déjà vérifiés dans library/audio (copiés, crédit conservé).

Chaque son est converti une fois : mono 44,1 kHz 16 bit, silences de tête et de queue coupés, fondus de bord, pic à -3 dBFS ; les boucles gardent leur longueur (le chargeur les boucle avec fondu).
Chaque banque écrit `library/audio_real/banks/<banque>/CREDITS.json` (+ la licence recopiée) pour `tools/export_commercial.py`."""
import argparse, hashlib, json, os, subprocess, sys, shutil
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.audio import library as L

SR = 44100
OUT = ROOT / 'library' / 'audio_real'
SRC = ROOT.parent / 'assets_externes' / 'sons'
OC = SRC / 'meta' / 'corpora' / 'oculus-audio-pack'
WY = SRC / 'wyzowl'
TODAY = '2026-10-30'


def decode(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:200])
    return np.frombuffer(r.stdout, np.float32).copy()


def process(a, loop=False, max_len=None):
    """coupe silences, garde la fenêtre la plus forte si trop long, fondus, pic -3 dBFS"""
    a = a - float(np.mean(a))
    pk = float(np.max(np.abs(a))) or 1.
    if not loop:
        thr = pk * 10 ** (-48 / 20); idx = np.nonzero(np.abs(a) > thr)[0]
        if len(idx): a = a[max(0, idx[0] - int(.008 * SR)):min(len(a), idx[-1] + int(.04 * SR))]
        if max_len and len(a) > max_len * SR:
            w = int(max_len * SR); hop = int(.1 * SR); env = np.convolve(np.abs(a), np.ones(int(.05 * SR)) / int(.05 * SR), 'same')
            best, bi = -1., 0
            for i in range(0, max(1, len(a) - w), hop):
                s = float(np.sum(env[i:i + w]))
                if s > best: best, bi = s, i
            a = a[bi:bi + w]
        fi, fo = int(.003 * SR), min(int(.03 * SR), len(a) // 3)
        if fi: a[:fi] *= np.linspace(0, 1, fi)
        if fo: a[-fo:] *= np.linspace(1, 0, fo)
        pk = float(np.max(np.abs(a))) or 1.; a = a * (0.708 / pk)
    else:
        a = a[:int(60 * SR)]; pk = float(np.max(np.abs(a))) or 1.; a = a * (0.5 / pk)
    return a.astype(np.float32)


def check(a, name):
    """silencieux, écrêté, tronqué ? -> liste de problèmes"""
    bad = []
    if len(a) < int(.03 * SR): bad.append('trop court')
    if float(np.max(np.abs(a))) < .05: bad.append('silencieux')
    if float(np.mean(np.abs(a) >= .999)) > .001: bad.append('écrêté')
    if abs(float(a[0])) > .2: bad.append('début abrupt')
    return bad


class Builder:
    def __init__(self, dry):
        self.dry = dry; self.events = {}; self.report = []; self.problems = []; self.banks = {}

    def add(self, event, src, bank, label, credit, loop=False, max_len=None, weight=1.0, ev_opts=None, name=None):
        a = process(decode(src), loop, max_len); pr = check(a, label)
        if pr: self.problems.append((event, label, pr)); return
        stem = (name or Path(src).stem).lower().replace(' ', '_').replace('(', '').replace(')', '')
        rel = f'sfx/{event}/{bank}_{stem}.wav'; sha = hashlib.sha256(Path(src).read_bytes()).hexdigest()[:16]
        if not self.dry:
            p = OUT / rel; p.parent.mkdir(parents=True, exist_ok=True); L.write_wav(str(p), a)
        e = self.events.setdefault(event, dict(loop=bool(loop), variants=[]))
        if ev_opts: e.update(ev_opts)
        e['variants'].append(dict(file=rel, weight=weight, credit=dict(credit, original=Path(src).name, sha256_source=sha)))
        self.banks.setdefault(bank, set()).add(event)
        self.report.append(dict(event=event, bank=bank, file=rel, dur=round(len(a) / SR, 2), peak=round(float(np.max(np.abs(a))), 3), rms=round(float(np.sqrt(np.mean(a * a))), 4)))


def oculus_index():
    idx = {}
    for f in sorted((OC / 'index').glob('*.json')):
        for s in json.loads(f.read_text(encoding='utf-8'))['sounds']: idx[s['id']] = s
    return idx


def pick(idx, *prefixes):
    """tous les sons dont l'identifiant commence par un des préfixes -> [(id, fichier ogg)]"""
    out = []
    for sid, s in idx.items():
        if any(sid.startswith(p) for p in prefixes):
            for t in s['takes']: out.append((sid, OC / 'ogg' / (Path(t['file']).stem + '.ogg')))
    return out


JIT = dict(pitch_jitter=40, gain_jitter_db=1.0)
OCULUS_MAP = {
    # pas : une prise = un pas
    'step_hard': (['FEETHmn_ShoeConcreteWalk'], JIT), 'step': (['FEETHmn_ShoeConcreteWalk'], JIT), 
    'step_wood': (['FEETHmn_ShoeWoodWalk'], JIT), 'step_grass': (['FEETHmn_ShoeGrassWalk'], JIT), 'footsteps_grass': (['FEETHmn_ShoeGrassWalk'], JIT),
    'footsteps_snow': (['FEETHmn_ShoeSnowWalk'], JIT), 'footsteps_gravel': (['FEETHmn_ShoeDirtWalk'], JIT), 'footsteps_sand': (['FEETHmn_ShoeDirtWalk'], JIT),
    'footsteps_heavy_step': (['FEETHmn_ShoeMetalWalk'], JIT), 'footsteps_run_step': (['FEETHmn_ShoeConcreteRun', 'FEETHmn_ShoeDirtRun'], JIT),
    'land': (['FEETHmn_ShoeConcreteLand', 'FEETHmn_ShoeWoodLand'], JIT), 'footsteps_metal': (['FEETHmn_ShoeMetalWalk'], JIT), 'footsteps_dirt': (['FEETHmn_ShoeDirtWalk'], JIT),
    # portes
    'door_slam': (['DOORWood_FrontDoorClose', 'DOORWood_OfficeDoorClose', 'DOORMetl_HatchClose', 'DOORGlas_GlassDoorClose'], {}),
    'door_open': (['DOORWood_FrontDoorOpen', 'DOORGlas_GlassDoorOpen', 'DOORSlid_SlidingDoorOpen', 'DOORMetl_HatchOpen'], {}),
    'door_handle': (['DOORHdwr_FrontDoorKnob', 'DOORHdwr_OfficeDoorKnob', 'DOORHdwr_GlassDoorKnob'], {}),
    'lock_rattle': (['DOORHdwr_FrontDoorLock', 'DOORHdwr_OfficeDoorLock', 'MECHLock_DoorLockKey', 'MECHLock_DoorUnlockKey'], {}),
    'knock': (['DOORKnck_OfficeDoorKnock'], {}), 'garage_door': (['DOORMetl_GarageDoor'], {}), 'drawer_open': (['DRWRWood_DrawerOpen'], {}), 'drawer_close': (['DRWRWood_DrawerClose'], {}),
    # horreur
    'creak': (['WOODFric_CreaksCreepy_'], {}), 'creak_far': (['WOODFric_CreaksCreepyReverb'], {}), 'skitter': (['METLFric_ScratchCreepy'], {}), 'chains': (['CHAINMvmt_ChainsCreepy'], {}),
    'growl': (['CREAMnstr_CreatureCreepy_'], {}), 'ghost_moan': (['VOXFem_GroanCreepy', 'CREAMnstr_CreatureCreepyReverb'], {}),
    'roar': (['CREAHmn_TrollDeathScream', 'CREAHmn_OgreDeathScream', 'CREAHmn_GiantDeathScream', 'CREAHmn_TrollEffort', 'CREAHmn_OgreEffort'], {}),
    'clock_tick': (['CLOCKTick_ClockCreepy_'], {}), 'impact_creepy': (['DSGNImpt_ImpactCreepyReverb'], {}), 'drone_creepy': (['DSGNDron_DroneCreepy'], dict(loop=True)),
    'breath': (['HMNBrth_'], {}), 'laugh': (['VOXLaff_Female', 'VOXLaff_Male'], {}), 'laugh_low': (['VOXLaff_EvilLaugh', 'CREAHmn_OgreLaugh', 'CREAHmn_TrollLaugh', 'CREAHmn_GiantLaugh'], {}),
    'scream': (['VOXFem_Female01DeathScream', 'VOXFem_Female02DeathScream'], {}), 'hurt': (['VOXFem_Female01Hurt', 'VOXFem_Female02Hurt'], {}), 'death': (['VOXFem_Female01Death_', 'VOXFem_Female02Death_'], {}),
    'effort': (['VOXEfrt_'], {}), 'pipe_organ_creepy': (['MUSCKeyd_PipeOrganCreepy'], {}),
    # objets
    'page_turn': (['PAPRHndl_BookPageTurns'], {}), 'paper': (['PAPRHndl_PaperCrumple', 'PAPRRip_PaperTear'], {}), 'glass_shatter': (['GLASBrk_GlassBottleBreak', 'GLASBrk_WindowPaneSmallBreak'], {}), 'glass_crack': (['GLASBrk_WindowPaneSmallBreak', 'GLASImpt_GlassBottleDrop'], {}),
    'metal_hit': (['METLImpt_MetalHitSurface', 'METLImpt_MetalObjDrop', 'METLImpt_CanDrop', 'METLImpt_BucketDrop'], {}), 'coin': (['OBJCoin_CoinDrop'], {}), 'key_drop': (['OBJKey_KeyDrop'], {}),
    'book_open': (['OBJBook_BookOpen'], {}), 'book_close': (['OBJBook_BookClose'], {}), 'switch_on': (['MECHSwtch_SwitchSmallOn'], {}), 'switch_off': (['MECHSwtch_SwitchSmallOff'], {}), 'lever': (['MECHLvr_LeverPull'], {}),
    'cloth': (['CLOTHMvmt_ClothingMovement', 'CLOTHMvmt_MovementWithGear'], {}), 'wood_drop': (['WOODImpt_LargeWoodDrop'], {}), 'wood_drag': (['WOODFric_LargeWoodMetalDrag'], {}), 'bushes': (['VEGELeaf_MovementThroughBushes'], {}),
    'sword_clash': (['WEAPSwrd_SwordClash'], {}), 'sword_draw': (['WEAPSwrd_SwordScrape', 'WEAPSwrd_Sword_'], {}), 'knife_scrape': (['WEAPKnif_KnifeScrape'], {}), 'axe_chop': (['WEAPAxe_WoodCutAxe'], {}),
    'punch': (['FGHTImpt_PunchRegular', 'FGHTImpt_PunchHarder', 'FGHTImpt_PunchHardest'], {}), 'kick': (['FGHTImpt_Kick'], {}), 'bones_break': (['GOREBone_BonesBreaking', 'GOREBone_SkullCracking'], {}), 'squish': (['GORESqsh_BloodSquishSlimy'], {}),
    'dog_bark': (['ANMLDog_DogBark', 'ANMLDog_DogAttention'], {}), 'horse_neigh': (['ANMLHors_'], {}), 'pig_squeal': (['ANMLFarm_PigSqueal'], {}), 'sheep': (['ANMLFarm_Sheep'], {}), 'chicken': (['BIRDFowl_Chicken'], {}),
    'whoosh': (['WHSH_WhooshMedium', 'WHSH_WhooshSmall'], {}), 'swoosh': (['SWSH_Swoosh'], {}), 'rowing': (['BOATRow_'], {}), 'servo': (['MOTRSrvo'], {}),
    'car_door_open': (['VEHDoor_CarDoorOpen'], {}), 'car_door_close': (['VEHDoor_CarDoorClose', 'VEHDoor_CarTrunkClose'], {}), 'car_start': (['VEHCar_CarStartRunStop'], {}),
    'engine': (['VEHCar_CarEngineSlow'], dict(loop=True)), 'faucet_on': (['WATRPlmb_FaucetOn'], {}), 'faucet_off': (['WATRPlmb_FaucetOff'], {}), 'toilet_flush': (['WATRPlmb_ToiletFlush'], {}),
    'train_pass': (['TRNElec_TrainPassby', 'TRNSbwy_SubwayPassbyEnter'], {}), 'elevator_door': (['DOORSlid_SlidingDoor'], {}),
}
OCULUS_AMB = {   # lits d'ambiance longs (boucles) : clé = amb_<nom d'ambiance du moteur>
    'amb_forest': ['AMBForst_Forest_LOOP'], 'amb_night': ['AMBForst_Night_LOOP'], 'amb_room': ['AMBHome_RoomTone'], 'amb_city': ['AMBUrbn_CityAmerican', 'AMBUrbn_CityEuroDaytime'],
    'amb_beach': ['AMBSea_BeachWavesStonesBirds'], 'amb_river': ['WATRFlow_River'], 'amb_rain': ['RAIN_CityRain', 'RAINVege_ForestRain'], 'amb_storm': ['RAIN_CityRain'],
    'amb_wind': ['WINDVege_LightWindTreesBirds'], 'amb_countryside': ['AMBFarm_FarmGeneric', 'WINDVege_WindTreesBirdsFlies'], 'amb_cafe': ['CRWDConv_Restaurant'], 'amb_crowd': ['CRWDConv_Restaurant'],
    'amb_waterfall': ['WATRFall_Waterfall'], 'amb_lake': ['AMBLake_LakeShore'], 'amb_creek': ['WATRFlow_CreekInWoods'], 'amb_underwater': ['AMBUndwtr_Underwater'], 'amb_machine_room': ['AMBInd_RoomToneMachineRoom'],
    'amb_construction': ['AMBCnst_ConstructionSiteMedium'], 'amb_cabin_rain': ['RAINInt_ForestCabinRain'], 'amb_faucet': ['WATRPlmb_FaucetWaterRun'], 'amb_wind_chimes': ['MUSCChim_WindChimes'],
}
WYZOWL_MAP = {   # sons dessinés CC0 (id de sounds.json -> clé du moteur)
    'boom': ['boom-hit-soft', 'boom-hit-medium', 'boom-hit-strong', 'boom-drop-soft'], 'impact': ['impact-medium-firm', 'impact-medium-hard', 'impact-heavy-firm', 'impact-light-hard'],
    'thump': ['impact-heavy-soft', 'impact-deep-soft', 'impact-medium-soft'], 'thunder': ['cinematic-thunder-big', 'cinematic-thunder-massive'], 'thunder_close': ['cinematic-thunder-big'],
    'explosion': ['cinematic-slam-big', 'cinematic-drum-big', 'boom-drop-strong'], 'collapse': ['bass-rumble-medium', 'boom-drop-medium'], 'rumble': ['bass-rumble-short', 'bass-rumble-medium', 'bass-rumble-long'],
    'whoosh_rev': ['reverse-whoosh-short-soft', 'reverse-whoosh-medium-soft', 'reverse-whoosh-short-strong'], 'riser': ['riser-2s-soft', 'riser-4s-soft', 'riser-2s-strong'],
    'doorbell': ['props-doorbell'], 'shop_bell': ['props-shop-bell'], 'drip': ['props-drip'], 'splash': ['props-splash'], 'phone_ring': ['phone-ring-classic', 'phone-ring-modern'],
    'phone_vibrate': ['phone-vibrate-table', 'phone-vibrate-hand'], 'typing': ['keyboard-typing-steady-medium', 'keyboard-typing-quick-medium'], 'camera_shutter': ['mechanical-shutter-heavy', 'mechanical-shutter-light'],
    'click': ['mechanical-switch-heavy', 'mechanical-switch-light'], 'button': ['mechanical-latch-light'], 'cloth_slide': ['foley-fabric-slide'], 'zip': ['props-zip'], 'scissors': ['props-scissors'],
}
WY_WHOOSH = ['whoosh-slow-soft', 'whoosh-medium-soft', 'whoosh-fast-soft', 'whoosh-medium-medium']


def run(only, dry):
    if not dry and only is None and (OUT / 'sfx').exists(): shutil.rmtree(OUT / 'sfx')        # reconstruction complète : pas de fichier orphelin d'une ancienne correspondance
    b = Builder(dry); idx = oculus_index()
    cred_oc = dict(source='Oculus Audio Pack 01 (Meta Open Sound)', url='https://github.com/facebookincubator/Meta-open-sound/tree/main/corpora/oculus-audio-pack', author='Oculus VR, LLC', licence='CC-BY-4.0',
                   redistribute=True, kind='recording', bank='oculus', credit_required=True, verified=f'{TODAY} : LICENSE du dépôt lu : CC BY 4.0, usage commercial permis avec crédit ; OGG = aperçus transcodés des WAV d\'origine')
    cred_wy = dict(source='SFX Kit (Wyzowl)', url='https://github.com/wyzowl/sfx-kit', author='Wyzowl', licence='CC0-1.0', redistribute=True, kind='designed', bank='wyzowl', credit_required=False,
                   verified=f'{TODAY} : LICENSE du dépôt lue : CC0 1.0, aucun crédit exigé ; sons « originaux » dessinés par l\'éditeur (pas des enregistrements de terrain)')
    if only in (None, 'oculus'):
        for ev, (prefixes, opts) in OCULUS_MAP.items():
            o = dict(opts); loop = o.pop('loop', False)
            for sid, f in pick(idx, *prefixes):
                if not f.exists(): continue
                b.add(ev, f, 'oculus', sid, cred_oc, loop=loop, max_len=(3.2 if ev in ('breath', 'creak', 'creak_far', 'growl', 'ghost_moan', 'roar', 'laugh', 'laugh_low') else 2.5 if ev in ('car_start', 'train_pass') else None), ev_opts=o or None)
        for ev, prefixes in OCULUS_AMB.items():
            for sid, f in pick(idx, *prefixes):
                if f.exists(): b.add(ev, f, 'oculus', sid, cred_oc, loop=True, ev_opts=dict(match='rms', target_rms=0.05))
    if only in (None, 'wyzowl'):
        S = {s['id']: s for s in json.loads((WY / 'sounds.json').read_text(encoding='utf-8'))['sounds']}
        for ev, ids in list(WYZOWL_MAP.items()) + [('whoosh', WY_WHOOSH)]:
            for sid in ids:
                s = S.get(sid)
                if s and (WY / s['file']).exists(): b.add(ev, WY / s['file'], 'wyzowl', sid, cred_wy, ev_opts=(dict(match='rms', target_rms=0.06) if ev in ('rumble',) else None))
    if only in (None, 'wikimedia'):
        old = json.loads((ROOT / 'library' / 'audio' / 'manifest.json').read_text(encoding='utf-8'))
        for ev, e in (old.get('events') or {}).items():
            for v in e.get('variants', []):
                c = v.get('credit') or {}
                if c.get('kind') != 'recording': continue
                src = ROOT / 'library' / 'audio' / v['file']
                if not src.exists(): continue
                if not dry:
                    d = OUT / 'sfx' / ev; d.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, d / ('wikimedia_' + Path(v['file']).name))
                ee = b.events.setdefault(ev, dict(loop=bool(e.get('loop')), variants=[]))
                for k in ('align', 'pitch_jitter', 'gain_jitter_db'):
                    if k in e: ee.setdefault(k, e[k])
                ee['variants'].append(dict(v, file=f"sfx/{ev}/wikimedia_{Path(v['file']).name}", credit=dict(c, bank='wikimedia', credit_required=False)))
                b.banks.setdefault('wikimedia', set()).add(ev)
    return b


def write(b):
    OUT.mkdir(parents=True, exist_ok=True)
    man = dict(version=1, defaults=dict(match='synth_short', align='attack', gain_db=0.0, target_rms=0.06), note='Vrais sons du moteur VOXEL (voir tools/sfx_bank_import.py). Lu par SoundLibrary(root=library/audio_real).', events=b.events)
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding='utf-8')
    meta = {
        'oculus': dict(name='Oculus Audio Pack 01', author='Oculus VR, LLC', source='https://github.com/facebookincubator/Meta-open-sound', license='Creative Commons Attribution 4.0 International (CC BY 4.0)', license_url='https://creativecommons.org/licenses/by/4.0/',
                       credit_required=True, commercial_ok=True, role='production', kind='recording',
                       credit_text='"Oculus Audio Pack 01" by Oculus VR, LLC (https://developers.meta.com/vr/downloads/package/oculus-audio-pack-1/), licensed under CC BY 4.0. Files renamed to the UCS naming convention; OGG previews transcoded from the original WAVs. Sounds trimmed, normalised and converted to mono 44.1 kHz.'),
        'wyzowl': dict(name='SFX Kit', author='Wyzowl', source='https://github.com/wyzowl/sfx-kit', license='CC0 1.0 Universal', license_url='https://creativecommons.org/publicdomain/zero/1.0/', credit_required=False, commercial_ok=True, role='production', kind='designed', credit_text=''),
        'wikimedia': dict(name='Wikimedia Commons (7 enregistrements)', author='stephan, ezwa, Knites, Mx. Granger (voir library/audio/LICENSES.md)', source='https://commons.wikimedia.org/', license='CC0 / domaine public (vérifié fichier par fichier)', credit_required=False, commercial_ok=True, role='production', kind='recording', credit_text=''),
    }
    for bank, evs in b.banks.items():
        d = OUT / 'banks' / bank; d.mkdir(parents=True, exist_ok=True)
        m = dict(meta[bank], events=sorted(evs), files=sum(1 for e in b.events.values() for v in e['variants'] if v['credit'].get('bank') == bank))
        (d / 'CREDITS.json').write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding='utf-8')
    lic = {'oculus': SRC / 'meta' / 'corpora' / 'oculus-audio-pack' / 'LICENSE', 'wyzowl': WY / 'LICENSE'}
    for bank, p in lic.items():
        if bank in b.banks and p.exists(): shutil.copyfile(p, OUT / 'banks' / bank / 'LICENSE.txt')
    (OUT / 'IMPORT_REPORT.json').write_text(json.dumps(dict(files=b.report, rejected=[dict(event=e, file=f, why=w) for e, f, w in b.problems]), indent=1, ensure_ascii=False), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry', action='store_true'); ap.add_argument('--only', choices=['oculus', 'wyzowl', 'wikimedia']); a = ap.parse_args()
    b = run(a.only, a.dry)
    nv = sum(len(e['variants']) for e in b.events.values())
    print(f"{len(b.events)} événements, {nv} variantes ; banques : { {k: len(v) for k, v in b.banks.items()} } ; rejetés : {len(b.problems)}")
    for e, f, w in b.problems[:12]: print('  rejeté', e, f, w)
    if not a.dry: write(b); print('écrit :', OUT)


if __name__ == '__main__': main()
