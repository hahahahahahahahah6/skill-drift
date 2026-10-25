"""Offline heuristic checks; never executes package code."""
from collections import Counter
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import re
from .skills import discover, read_skill

@dataclass
class Finding:
    skill: str
    file: str
    line: int
    kind: str
    claim: str
    severity: str
    detail: str

TOKEN = re.compile(r'`([^`\n]+)`|([^\s`<>"\']+)')
EXT = re.compile(r'\.(py|js|ts|md|json|yaml|yml|toml|sh|go|rs|txt)$')
DIR = re.compile(r'^(?:\./)?(?:scripts|references|examples|tests|docs|bin)/')


def claims(line):
    for match in TOKEN.finditer(line):
        token = (match[1] or match[2]).strip('()[]{}.,;:!?')
        if token.startswith(('http://', 'https://', '/', '~/', '\\')) or '*' in token or re.match(r'^[A-Za-z]:[/\\]', token):
            continue
        if '/' in token and (EXT.search(token) or DIR.match(token)):
            yield token


def audit(root, fail_on='high', ignore=(), limit=500):
    root = Path(root).resolve()
    packages = [read_skill(p) for p in discover(root)]
    findings = []
    errors = []
    names = Counter(s.metadata.get('name') for s in packages if s.metadata.get('name'))
    ignored = 0
    seen = set()
    for skill in packages:
        relative = skill.directory.relative_to(root).as_posix()
        if skill.error:
            errors.append({'skill': relative, 'file': 'SKILL.md', 'line': 1, 'detail': skill.error})
            continue
        def add(line, kind, claim, severity, detail):
            nonlocal ignored
            key = (relative, line, kind, claim)
            if key in seen:
                return
            seen.add(key)
            if any(fnmatchcase(claim, pattern) for pattern in ignore):
                ignored += 1
                return
            findings.append(Finding(relative, 'SKILL.md', line, kind, claim, severity, detail))
        if skill.missing_frontmatter:
            add(1, 'missing-frontmatter', 'frontmatter', 'HIGH', 'Expected opening --- frontmatter line')
        else:
            for key in ('name', 'description'):
                if not skill.metadata.get(key, '').strip():
                    add(1, 'missing-' + key, key, 'HIGH', 'Required nonempty frontmatter field')
            name = skill.metadata.get('name')
            if name and name != skill.directory.name:
                add(2, 'name-mismatch', name, 'MEDIUM', 'Directory name is ' + skill.directory.name)
            if name and names[name] > 1:
                add(2, 'duplicate-skill-name', name, 'MEDIUM', 'Name occurs in multiple skill packages')
        if len(skill.body.strip()) < 50:
            add(skill.body_line, 'empty-body', 'body', 'MEDIUM', 'Body is shorter than 50 characters')
        for number, line in enumerate(skill.body.splitlines(), skill.body_line):
            for claim in claims(line):
                local = skill.directory / claim
                target = local if local.exists() else root / claim
                exists = target.is_dir() if claim.endswith('/') else target.exists()
                if not exists:
                    add(number, 'referenced-file', claim, 'HIGH', 'Referenced path does not exist')
                elif re.match(r'^(?:\./)?scripts/', claim) and target.is_file():
                    try:
                        shebang = target.open('rb')
                        with shebang:
                            starts = shebang.read(2) == b'#!'
                        if not target.stat().st_mode & 0o111 and not starts:
                            add(number, 'script-not-executable', claim, 'MEDIUM', 'No executable bit and no shebang')
                    except OSError as error:
                        errors.append({'skill': relative, 'file': claim, 'line': number, 'detail': str(error)})
    findings.sort(key=lambda f: (f.skill, f.line, f.kind, f.claim))
    # Verdict considers all findings, including those beyond the display cap.
    failed = bool(errors) or any(f.severity == 'HIGH' or fail_on == 'medium' for f in findings)
    code = 2 if failed else (1 if findings else 0)
    return {'skills_found': len(packages), 'totals': {'kind': dict(sorted(Counter(f.kind for f in findings).items())), 'severity': dict(sorted(Counter(f.severity for f in findings).items()))}, 'findings': [asdict(f) for f in findings[:limit]], 'ignored_count': ignored, 'parse_error_count': len(errors), 'parse_errors': errors, 'truncated': len(findings) > limit, 'omitted_count': max(0, len(findings)-limit), 'verdict': ('FAIL' if code == 2 else 'WARN' if code == 1 else 'PASS'), 'exit_code': code, 'note': 'no skills found' if not packages else ''}
