"""Real 9:16 MP4 of the two demos that crashed, rendered on the CONSOLE 2D engine.

Local only: the scratch voice is the formant synthesiser of hstudio/audio/scratch_voice.py, no TTS, no API.
The projects are built under names of their own (console_cam_*) so no render the owner kept is overwritten.

The `if __name__ == '__main__'` guard is not decoration: step_render() renders the frames in a process pool,
and on Windows a pool worker re-imports this module. Without the guard each worker would replay the whole
script and the render would deadlock instead of starting.

  python tools/_mp4_proof_console_camera.py
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)


def main():
    os.chdir(ROOT)
    import shutil
    from hstudio import demos
    from hstudio.pipeline import Project, load_settings, step_mix, step_render, step_qc

    out_all = {}
    for demo_id in ('demo2_dialogue', 'demo3_groupe'):
        slug = 'console_cam_' + demo_id
        d = os.path.join(ROOT, 'projects', slug)
        if os.path.isdir(d): shutil.rmtree(d)        # a half-built project from an interrupted run
        pr = demos.prepare(demo_id, slug=slug, name='CONSOLE 2D ' + demo_id)
        pr.meta['style'] = 'console'                 # the engine under test, not the demo's native PIXEL 3D
        pr.save()
        s = dict(load_settings()); s['workers'] = int(os.environ.get('MP4_WORKERS', '6'))
        step_mix(pr, s)
        step_qc(pr, s, '9:16')
        mp4 = step_render(pr, s, '9:16', 'standard')
        out_all[demo_id] = dict(mp4=mp4, verify=pr.read_json('verify_short_9x16.json'),
                                qc=pr.read_json('qc_9x16.json', {}).get('summary'))
        print('>>>', demo_id, '->', mp4, os.path.getsize(mp4), 'octets')
    json.dump(out_all, open(os.path.join(ROOT, 'docs', 'console_camera_mp4.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False, default=str)
    print(json.dumps(out_all, indent=1, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
