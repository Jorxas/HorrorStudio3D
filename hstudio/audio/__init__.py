# sounds for stories of every genre (animals, city, magic, comedy...) are defined in ambience.py and registered here
from . import synth as _synth, ambience as _ambience
_synth.SFX.update(_ambience.EXTRA_SFX); _synth.SFX_DESCRIPTIONS.update(_ambience.EXTRA_DESCRIPTIONS); _synth.LONG_SFX = _ambience.LONG_SFX
# real bruitages: library/audio/manifest.json answers first for the keys it covers, synthesis stays the fallback
from . import library as _library
_synth.SAMPLE_PROVIDER = _library.provider
LIB = _library.LIB
