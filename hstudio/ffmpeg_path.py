"""Finds ffmpeg and ffprobe when the shell PATH does not. A per-user install (winget, scoop, chocolatey,
~/.local/bin) is not visible to shells started before the install, so the folder is looked up here and prepended
to PATH for this process only -- nothing on the machine is modified. The whole pipeline calls plain 'ffmpeg' and
'ffprobe' (including through os.system and shell=True), so this single fix covers every call site.

Override the lookup with HSTUDIO_FFMPEG_DIR=<folder holding ffmpeg and ffprobe>."""
import os, glob, shutil

EXE = '.exe' if os.name == 'nt' else ''
TOOLS = ('ffmpeg', 'ffprobe')
INSTALL_HINT = ('Windows : winget install --id Gyan.FFmpeg --exact --scope user'
                '  |  macOS : brew install ffmpeg  |  Linux : sudo apt install ffmpeg')

def _candidates():
    """Usual per-user install folders, best first; HSTUDIO_FFMPEG_DIR always wins."""
    home, env = os.path.expanduser('~'), os.environ.get
    if env('HSTUDIO_FFMPEG_DIR'): yield env('HSTUDIO_FFMPEG_DIR')
    if os.name == 'nt':
        local = env('LOCALAPPDATA') or os.path.join(home, 'AppData', 'Local')
        yield os.path.join(local, 'Microsoft', 'WinGet', 'Links')
        # winget portable packages keep the real binaries under Packages/<id>/<build>/bin ; newest build first
        yield from sorted(glob.glob(os.path.join(local, 'Microsoft', 'WinGet', 'Packages', '*FFmpeg*', '**', 'bin'), recursive=True), reverse=True)
        yield os.path.join(local, 'Programs', 'ffmpeg', 'bin')
        yield os.path.join(home, 'scoop', 'shims')
        yield os.path.join(env('ProgramData') or r'C:\ProgramData', 'chocolatey', 'bin')
        yield r'C:\ffmpeg\bin'
    else:
        yield '/opt/homebrew/bin'; yield '/usr/local/bin'
    yield os.path.join(home, '.local', 'bin')

def _complete(d):
    """True only if the folder holds both tools : an ffmpeg without its ffprobe breaks the pipeline later on."""
    return bool(d) and os.path.isdir(d) and all(os.path.isfile(os.path.join(d, t + EXE)) for t in TOOLS)

def ensure():
    """Makes both tools reachable for this process. Returns {'ffmpeg': path or None, 'ffprobe': path or None}."""
    found = {t: shutil.which(t) for t in TOOLS}
    if all(found.values()): return found
    for d in _candidates():
        if _complete(d):
            os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
            return {t: shutil.which(t) for t in TOOLS}
    return found
