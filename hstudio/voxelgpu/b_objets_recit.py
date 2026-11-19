"""Native box volumes for the story-phone props; their images are shared with PS1."""
from ..engines.pixel3d import objets_recit as K


def h_long_fingers(col,cfg):
    P=lambda x,y,z:(x,y,z)
    return K.h_long_fingers(P,{}, {},None,col,cfg),[]


def enregistrer(R):
    R.objet('od_camera_view',lambda p:K.k_camera_view(p,None))
    R.objet('od_phone_flash',lambda p:K.k_phone_flash(p,None))
    R.tenu('od_long_fingers',h_long_fingers)
    R.tenu('od_food_box',lambda col,cfg:(K.h_food_box(lambda x,y,z:(x,y,z),{},{},None,col,cfg),[]))
