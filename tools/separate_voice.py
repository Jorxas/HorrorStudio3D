"""Séparer la voix d'une chanson (étape 1 du module « représentation musicale »).

    <python avec torch> tools/separate_voice.py chanson.m4a sortie_dossier
      -> sortie_dossier/voix.wav (la voix seule), accompagnement.wav, drums.wav, bass.wav

Refait le 31/10/2026 : le script d'origine n'a pas été retrouvé sur ce PC. Modèle : Hybrid Demucs
(torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS, MUSDB-HQ + données en plus), sur la carte graphique si elle est là.
Les poids (~330 Mo) se téléchargent une fois dans le cache de torch. Il faut un Python avec torch + torchaudio
(sur ce PC : Desktop\\Studium\\Perso\\MainClip\\PPS\\.venvs\\chatterbox\\Scripts\\python.exe).
"""
import os, subprocess, sys
import torch, torchaudio
from torchaudio.transforms import Fade


def load(path, sr):
    """n'importe quel format que ffmpeg lit -> tenseur (2, n) à `sr`"""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '2', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(-1, 2).T.contiguous()


def separate(model, mix, sr, dev, segment=10., overlap=.1):
    """découpe en segments qui se recouvrent (fondus), comme l'exemple officiel de torchaudio"""
    batch, ch, length = mix.shape
    chunk = int(sr * segment * (1 + overlap)); start, end = 0, chunk; ov = int(overlap * sr)
    fade = Fade(fade_in_len=0, fade_out_len=ov, fade_shape='linear')
    out = torch.zeros(batch, len(model.sources), ch, length, device=dev)
    while start < length - ov:
        part = mix[:, :, start:end]
        with torch.no_grad(): o = model.forward(part)
        o = fade(o); out[:, :, :, start:end] += o
        if start == 0: fade.fade_in_len = ov; start += int(chunk - ov)
        else: start += chunk
        end += chunk
        if end >= length: fade.fade_out_len = 0
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True)
    bundle = torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS; sr = bundle.sample_rate
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = bundle.get_model().to(dev).eval()
    wav = load(src, sr).to(dev)
    ref = wav.mean(0); wav = (wav - ref.mean()) / ref.std()
    stems = separate(model, wav[None], sr, dev)[0] * ref.std() + ref.mean()
    S = dict(zip(model.sources, stems))
    voice = S['vocals'].cpu(); acc = sum(v for k, v in S.items() if k != 'vocals').cpu()
    torchaudio.save(os.path.join(dst, 'voix.wav'), voice, sr)
    torchaudio.save(os.path.join(dst, 'accompagnement.wav'), acc, sr)
    for k in ('drums', 'bass'):
        if k in S: torchaudio.save(os.path.join(dst, k + '.wav'), S[k].cpu(), sr)
    print('séparé sur', dev, ':', ', '.join(model.sources), '->', dst)


if __name__ == '__main__':
    main()
