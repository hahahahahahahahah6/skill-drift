"""Command line interface."""
import argparse
import json
from . import __version__
from .audit import audit


def main(argv=None):
    parser = argparse.ArgumentParser(prog='skill-drift', description='Audit skill package claims offline')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('audit')
    command.add_argument('path', nargs='?', default='.')
    command.add_argument('--json', action='store_true')
    command.add_argument('--fail-on', choices=('high', 'medium'), default='high')
    command.add_argument('--ignore', action='append', default=[], metavar='G')
    args = parser.parse_args(argv)
    try:
        report = audit(args.path, args.fail_on, args.ignore)
    except (ValueError, OSError) as error:
        report = {'skills_found': 0, 'totals': {'kind': {}, 'severity': {}}, 'findings': [], 'ignored_count': 0, 'parse_error_count': 1, 'parse_errors': [{'skill': '.', 'file': 'SKILL.md', 'line': 1, 'detail': str(error)}], 'truncated': False, 'omitted_count': 0, 'verdict': 'FAIL', 'exit_code': 2, 'note': ''}
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print('%s: %s skills found' % (report['verdict'], report['skills_found']))
        if report['note']:
            print(report['note'])
        for finding in report['findings']:
            print('{skill}:{file}:{line}: {severity} {kind}: {claim} — {detail}'.format(**finding))
        for error in report['parse_errors']:
            print('{skill}:{file}:{line}: parse error: {detail}'.format(**error))
        print('Totals: ' + json.dumps(report['totals'], sort_keys=True))
        print('Ignored: %s; parse errors: %s; truncated: %s (omitted %s)' % (report['ignored_count'], report['parse_error_count'], report['truncated'], report['omitted_count']))
    return report['exit_code']
