"""No network: image integrity, physical flash timing, reveal faces and registry."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib,numpy as np
from PIL import Image
from hstudio.engines.pixel3d import objets_tex as T,assets as A,sets,effects
from hstudio.voxelgpu import b_objets


def main():
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/'screen.png';Image.new('RGB',(40,60),(12,100,180)).save(p)
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        a=T.image_locale(str(p),sha)
        assert a.shape==(144,80,4) and list(a[0,0])==[12,100,180,255]
        try:T.image_locale(str(p),'0'*64)
        except ValueError:pass
        else:raise AssertionError('Changed image was accepted')
    o={'type':'mover','thing':'prop:od_phone_flash','path':[[1,1.5,2],[1,1.5,2]],
       'start':1,'dur':.1,'wait':False,'stay':False,'pitch':0,'bank':0}
    for t,visible in ((.9,False),(1.04,True),(1.2,False)):
        bx,lights=effects.mover(SimpleNamespace(T=t,g=t),o)
        assert bool(bx)==visible and bool(lights)==visible
        if visible:assert np.allclose(lights[0][0],[1,1.5,2])
    p=A.face_tex('predator');s=A.face_tex('predator_smile');normal=A.face_tex('happy')
    assert not np.array_equal(p,s) and not np.array_equal(normal,p)
    assert 'od_camera_view' in sets.PROP_TYPES
    assert 'od_long_fingers' in b_objets.HELD_VOX
    from hstudio.qa.editorial import known_names
    names=known_names('ps1')['hold']
    assert {'od_long_fingers','od_food_box','od_wine_glass','od_kitchen_knife'} <= names
    assert 'od_camera_view' not in names  # Placed-only props remain rejected in a hand.
    print('Écran : empreinte et pixels OK ; flash : source et durée OK ; révélations et deux registres OK.')


if __name__=='__main__':main()
