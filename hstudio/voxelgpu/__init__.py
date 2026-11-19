"""Unified engine: Horror Studio (B) directs, the voxel engine (A, Three.js on the GPU) paints.

    python -m hstudio.voxelgpu check              # GPU attestation + micro render + contract round trip
    python -m hstudio.voxelgpu build  ep.json out_contract.json
    python -m hstudio.voxelgpu render ep_or_contract.json out.mp4 [--aspect 9:16] [--audio a.wav]
    python -m hstudio.voxelgpu verify out.mp4

B keeps the script, the régie (paths, speeds, gestures, speech behaviour), the cinematographer and the QA; A keeps the
characters (rigs, faces, hands, clothes), the worlds, the lighting and the post-processing. The two meet in one JSON
contract (hstudio/voxelgpu/contract.py). Neither original engine is modified: A is copied to voxelgpu_js/ and B is imported.
"""
