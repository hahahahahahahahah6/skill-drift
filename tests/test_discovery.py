import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from skill_drift.skills import discover, read_skill

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def skill(self, path='demo', text=None):
        p = self.root / path
        p.mkdir(parents=True, exist_ok=True)
        (p/'SKILL.md').write_text(text if text is not None else '---\nname: demo\ndescription: test\n---\nBody', encoding='utf-8')
        return p
    def test_root(self):
        self.skill('.')
        self.assertEqual(discover(self.root), [self.root])
    def test_nested(self):
        self.assertEqual(discover(self.root), [])
        self.skill('a/b')
        self.assertEqual(len(discover(self.root)), 1)
    def test_hidden(self):
        self.skill('.claude/skills/demo')
        self.skill('.cursor/skills/demo')
        self.assertEqual(len(discover(self.root)), 2)
    def test_skips(self):
        for d in ('.git','node_modules','dist','__pycache__','.venv','venv'):
            self.skill(d+'/demo')
        self.assertEqual(discover(self.root), [])
    def test_exact_case(self):
        (self.root/'skill.md').write_text('test')
        self.assertEqual(discover(self.root), [])
    def test_sorted(self):
        self.skill('z'); self.skill('a')
        self.assertEqual([p.name for p in discover(self.root)], ['a','z'])
    def test_bad_path(self):
        with self.assertRaises(ValueError): discover(self.root/'absent')
    def test_bad_utf8(self):
        p = self.skill(); (p/'SKILL.md').write_bytes(b'\xff')
        self.assertTrue(read_skill(p).error)
    def test_permission_error(self):
        p = self.skill()
        with patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
            self.assertIn('denied', read_skill(p).error)
    def test_quotes_lists(self):
        s = read_skill(self.skill(text='---\nname: "demo"\ndescription: \'test\'\nfiles:\n  - a.md\n  - "b.md"\n---\nBody'))
        self.assertFalse(s.error)
        self.assertEqual(s.metadata['files'], ['a.md','b.md'])
    def test_missing_close(self):
        self.assertTrue(read_skill(self.skill(text='---\nname: demo')).error)
    def test_complex_yaml(self):
        for field in ('description: |','description: >','description: &anchor value','description: {a: b}','description: [a, b]','extra:\n  nested: value','description: *anchor'):
            with self.subTest(field=field):
                self.assertTrue(read_skill(self.skill(text='---\nname: demo\n'+field+'\n---\nBody')).error)
    def test_duplicate_key(self):
        self.assertTrue(read_skill(self.skill(text='---\nname: a\nname: b\n---\nBody')).error)
    def test_unterminated_quote(self):
        self.assertTrue(read_skill(self.skill(text='---\nname: "demo\n---\nBody')).error)
