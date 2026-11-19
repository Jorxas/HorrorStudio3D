"""Capabilities (V3): what the engines can represent, what a scene needs, and how missing capabilities are added.

registry.py    the capabilities, read from the code itself (+ extensions)
lexicon.py     words of a story -> needs (also names what does not exist yet)
planner.py     Scene Capability Planner: needs -> available / composed / partial / missing -> extension requests
audit.py       an episode checked before the validator repairs it: every gap reported with its consequence
extensions.py  level 2: capabilities added as tested, fingerprinted extensions (library/extensions/<id>)"""
