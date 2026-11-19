"""Automatic quality control of DIRECTED scenes (PS1 / VOXEL / CONSOLE): detect, explain in French, fix what is safe to fix,
refuse to render on blocking errors. See docs/QA_SCENE.md; CLI: tools/verifier_scene.py.

    from hstudio import qa
    rep = qa.verify('dossier/episode')            # Report (never modifies the episode)
    qa.correct('dossier/episode')                 # corrected COPY + CORRECTIONS.md
    qa.gate('dossier/episode', style='ps1')       # what the render tools call first (False = refuse)

Modules: editorial (time, titles, names, speech), probe (the engine measured, nothing changed), checks (geometry, continuity,
image), fix (safe corrections on a copy), report (Issue / Report, markdown + json)."""
from .report import Issue, Report, BLOQUANT, A_REVOIR, INFO  # noqa: F401
from .run import verify, gate, write  # noqa: F401


def correct(folder, out=None, **kw):
    from .fix import correct as _c
    return _c(folder, out, **kw)
