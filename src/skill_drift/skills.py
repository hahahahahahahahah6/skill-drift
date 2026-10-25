"""Deterministic discovery and deliberately small frontmatter parser."""
from dataclasses import dataclass
from pathlib import Path
import os
import re

SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '.venv', 'venv'}

@dataclass
class Skill:
    directory: Path
    metadata: dict
    body: str
    body_line: int
    error: str = ''
    missing_frontmatter: bool = False


def discover(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('audit path must be an existing directory')
    found = []
    def walk_error(error):
        raise ValueError(str(error))
    for directory, dirs, files in os.walk(root, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        if 'SKILL.md' in files:
            found.append(Path(directory))
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def scalar(value):
    value = value.strip()
    if not value:
        return ''
    if value[0] in "\"'":
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError('unterminated quoted scalar')
        return value[1:-1]
    if re.search(r'(^|\s)[&*!]|:\s|^[>|\[\]{}]|^[-?]\s', value):
        raise ValueError('unsupported complex YAML scalar')
    return value


def read_skill(directory):
    directory = Path(directory)
    try:
        lines = (directory / 'SKILL.md').read_text(encoding='utf-8').splitlines()
        if not lines or lines[0] != '---':
            return Skill(directory, {}, '\n'.join(lines), 1, missing_frontmatter=True)
        try:
            end = lines.index('---', 1)
        except ValueError:
            raise ValueError('frontmatter has no closing --- line')
        metadata = {}
        current = None
        for number, line in enumerate(lines[1:end], 2):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            item = re.fullmatch(r'\s+-\s+(.+)', line)
            if item and current:
                if metadata[current] == '':
                    metadata[current] = []
                if not isinstance(metadata[current], list):
                    raise ValueError('list under nonempty scalar')
                metadata[current].append(scalar(item[1]))
                continue
            match = re.fullmatch(r'([A-Za-z_][\w-]*):\s*(.*)', line)
            if not match:
                raise ValueError('unsupported YAML at line %s' % number)
            current = match[1]
            if current in metadata:
                raise ValueError('duplicate frontmatter key: ' + current)
            metadata[current] = scalar(match[2])
        for key in ('name', 'description'):
            if key in metadata and not isinstance(metadata[key], str):
                raise ValueError(key + ' must be a scalar')
        return Skill(directory, metadata, '\n'.join(lines[end+1:]), end+2)
    except (OSError, UnicodeError, ValueError) as error:
        return Skill(directory, {}, '', 1, error=str(error))
