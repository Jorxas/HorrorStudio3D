"""Story props: a readable camera preview, a physical phone flash, and long fingertips."""
from . import objets as OD,objets_tex as T
from .r3d import B,C,M_FABRIC


def k_camera_view(p,c):
    if p.get('ecran')=='image':screen=T.image_locale(p['image_locale'],p['image_sha256'],80,136)
    else:screen=T.phone_screen('message','22:14','LUN. 2 NOV','AMIE',T.lines(p.get('texte',['PHOTO ?'])))
    case=(48,53,67);skin=tuple(p.get('skin',[184,137,108]))
    return [C((0,.25,0),(.30,.54,.035),case),
            C((0,.26,-.020),(.264,.455,.002),(24,28,36),tex={'-z':screen},texemis=.32,cast=False),
            C((0,.499,-.020),(.075,.018,.003),(10,12,18)),
            C((-.15,.12,.015),(.075,.20,.085),skin),C((.15,.10,.015),(.075,.20,.085),skin),
            C((-.17,-.07,.07),(.12,.30,.13),(181,181,174),mat=M_FABRIC),
            C((.17,-.09,.07),(.12,.30,.13),(181,181,174),mat=M_FABRIC)]


def k_phone_flash(p,c):
    # The light definition shares this lens centre. A timed mover switches both on/off together.
    return [C((0,0,0),(.017,.017,.006),(238,242,230),emis=4,cast=False)]


def h_long_fingers(P,F,k,lights,col,cfg):
    skin=tuple(cfg.get('peau',[167,178,160]));out=[]
    for j in range(4):
        x=-.045+j*.03;length=(.15,.20,.21,.17)[j]
        out += [C(P(x,-length/2-.035,.055),(.022,length,.025),skin,**k),
                C(P(x,-length-.04,.063),(.018,.055,.014),(61,59,46),**k)]
    return out


def h_food_box(P,F,k,lights,col,cfg):
    return [C(P(0,.015,.07),(.23,.085,.16),(154,167,172),**k),
            C(P(0,.062,.07),(.245,.018,.173),(78,122,137),**k),
            C(P(0,.076,.07),(.07,.012,.045),(55,87,102),**k)]


def enregistrer(R):
    R.objet('od_camera_view',k_camera_view,'téléphone en vue subjective (aperçu rendu)',[])
    R.objet('od_phone_flash',k_phone_flash,'flash du téléphone (source physique)',[((0,0,0),(.94,.97,1),6.,6.,False)])
    R.tenu('od_long_fingers',h_long_fingers,'doigts allongés et ongles')
    R.tenu('od_food_box',h_food_box,'boîte de restes fermée')
