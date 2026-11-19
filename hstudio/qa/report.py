"""Issues and reports of the scene QA (hstudio/qa). Messages are in French (they are read by the owner and by
the AI that wrote the scene); code and comments stay in English.

An Issue says WHERE (shot, camera setup, instant), WHAT (code + problem), WHY it is a problem, HOW to fix it
(the exact key to change, and when possible the value), and how serious it is:

    bloquant  : the film would show an error; the render tools refuse to start (unless --forcer)
    a_revoir  : probably an error, a human must look at the image
    info      : worth knowing, never an error on its own
"""
import json

BLOQUANT, A_REVOIR, INFO = 'bloquant', 'a_revoir', 'info'
ORDER = {BLOQUANT: 0, A_REVOIR: 1, INFO: 2}
LABEL = {BLOQUANT: 'BLOQUANT', A_REVOIR: 'À REVOIR', INFO: 'info'}


class Issue:
    __slots__ = ('code', 'severity', 'shot', 'setup', 't', 't_shot', 'who', 'msg', 'why', 'fix', 'key', 'value', 'auto', 'data', 'family')

    def __init__(self, code, severity, msg, why='', fix='', shot=None, setup=None, t=None, t_shot=None, who=None, key=None, value=None,
                 auto=False, family=None, **data):
        self.code, self.severity, self.msg, self.why, self.fix = code, severity, msg, why, fix
        self.shot, self.setup, self.t, self.t_shot, self.who = shot, setup, t, t_shot, who
        self.key, self.value, self.auto, self.family, self.data = key, value, bool(auto), family or code.split('.')[0], data

    def where(self):
        out = []
        if self.shot is not None: out.append(f'plan {self.shot}' + (f' (cadrage {self.setup})' if self.setup else ''))
        if self.t is not None: out.append(f'{self.t:.2f} s' + (f' (+{self.t_shot:.2f} s dans le plan)' if self.t_shot is not None else ''))
        if self.who: out.append(str(self.who))
        return ', '.join(out) or 'épisode'

    def to_json(self):
        d = {k: getattr(self, k) for k in self.__slots__ if k != 'data'}
        d['data'] = self.data
        for k in ('t', 't_shot'):
            if d[k] is not None: d[k] = round(float(d[k]), 3)
        return d


class Report:
    def __init__(self, episode_dir, aspect, style, mode):
        self.dir, self.aspect, self.style, self.mode = str(episode_dir), aspect, style, mode
        self.issues = []; self.notes = []; self.stats = {}

    def add(self, issue):
        self.issues.append(issue); return issue

    def note(self, msg): self.notes.append(msg)

    def merged(self):
        """the same defect seen at several instants of the same camera setup is ONE issue (first instant kept, count stored)"""
        seen = {}; out = []
        for i in sorted(self.issues, key=lambda i: (i.shot if i.shot is not None else -1, i.t if i.t is not None else -1)):
            key = (i.code, i.shot, i.setup, i.who, i.key)
            if key in seen:
                j = seen[key]; j.data['vu'] = j.data.get('vu', 1) + 1
                if ORDER[i.severity] < ORDER[j.severity]: j.severity = i.severity
                continue
            seen[key] = i; out.append(i)
        return out

    def counts(self, issues=None):
        issues = self.merged() if issues is None else issues
        return {s: sum(1 for i in issues if i.severity == s) for s in (BLOQUANT, A_REVOIR, INFO)}

    def blocking(self): return [i for i in self.merged() if i.severity == BLOQUANT]

    def ok(self): return not self.blocking()

    def to_json(self):
        iss = self.merged()
        return dict(dossier=self.dir, format=self.aspect, style=self.style, mode=self.mode, ok=self.ok(), comptes=self.counts(iss),
                    notes=self.notes, stats=self.stats, problemes=[i.to_json() for i in sorted(iss, key=_sort_key)])

    def markdown(self, title=None):
        iss = sorted(self.merged(), key=_sort_key); c = self.counts(iss)
        L = [f'# {title or "Contrôle qualité de la scène"}', '',
             f'- Dossier : `{self.dir}`', f'- Format : {self.aspect} — style : {self.style} — vérifications : {self.mode}',
             f'- Résultat : **{"REFUSÉ (erreurs bloquantes)" if c[BLOQUANT] else "accepté"}** — {c[BLOQUANT]} bloquant(s), {c[A_REVOIR]} à revoir, {c[INFO]} info', '']
        if self.stats:
            L += ['## Mesures', ''] + [f'- {k} : {v}' for k, v in self.stats.items()] + ['']
        if self.notes:
            L += ['## Remarques', ''] + [f'- {n}' for n in self.notes] + ['']
        for sev in (BLOQUANT, A_REVOIR, INFO):
            part = [i for i in iss if i.severity == sev]
            if not part: continue
            L += [f'## {LABEL[sev]} ({len(part)})', '']
            for i in part:
                vu = f' — vu {i.data["vu"]} fois' if i.data.get('vu', 1) > 1 else ''
                L.append(f'### [{i.code}] {i.where()}{vu}')
                L.append(f'- **Problème** : {i.msg}')
                if i.why: L.append(f'- **Pourquoi** : {i.why}')
                if i.fix: L.append(f'- **Comment corriger** : {i.fix}')
                if i.key: L.append(f'- **Clé** : `{i.key}`' + (f' → `{json.dumps(i.value, ensure_ascii=False)}`' if i.value is not None else ''))
                if i.auto: L.append('- Correction automatique possible (`--corriger`).')
                L.append('')
        if not iss: L += ['Aucun problème trouvé.', '']
        return '\n'.join(L)


def _sort_key(i):
    return (ORDER[i.severity], i.shot if i.shot is not None else -1, i.t if i.t is not None else -1, i.code)
