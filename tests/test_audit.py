import tempfile
import unittest
from pathlib import Path
from skill_drift.audit import audit

BODY = 'Follow this synthetic procedure carefully using local fixture data only. '

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def skill(self, name='demo', front=None, body=BODY):
        p = self.root/name; p.mkdir(parents=True, exist_ok=True)
        (p/'SKILL.md').write_text('---\n'+(front if front is not None else 'name: '+name+'\ndescription: synthetic')+'\n---\n'+body)
        return p
    def report(self, **kw): return audit(self.root, **kw)
    def kinds(self): return self.report()['totals']['kind']
    def test_good(self):
        self.skill(); self.assertEqual(self.report()['exit_code'], 0)
    def test_missing_frontmatter(self):
        p=self.skill(); (p/'SKILL.md').write_text(BODY)
        self.assertEqual(self.kinds(), {'missing-frontmatter':1}); self.assertEqual(self.report()['exit_code'],2)
    def test_missing_name(self):
        self.skill(front='description: synthetic'); self.assertEqual(self.kinds(), {'missing-name':1})
    def test_empty_name(self):
        self.skill(front='name: ""\ndescription: synthetic'); self.assertIn('missing-name',self.kinds())
    def test_missing_description(self):
        self.skill(front='name: demo'); self.assertEqual(self.report()['totals']['severity'], {'HIGH':1})
    def test_empty_description(self):
        self.skill(front='name: demo\ndescription:'); self.assertIn('missing-description',self.kinds())
    def test_mismatch_warn(self):
        self.skill(front='name: other\ndescription: synthetic'); self.assertEqual(self.report()['exit_code'],1)
    def test_mismatch_fail(self):
        self.skill(front='name: other\ndescription: synthetic'); self.assertEqual(self.report(fail_on='medium')['exit_code'],2)
    def test_missing_reference(self):
        self.skill(body=BODY+'`references/missing.md`'); self.assertEqual(self.kinds(), {'referenced-file':1})
    def test_existing_reference(self):
        p=self.skill(body=BODY+'references/a.md'); (p/'references').mkdir(); (p/'references/a.md').touch()
        self.assertEqual(self.report()['exit_code'],0)
    def test_script_no_exec(self):
        p=self.skill(body=BODY+'scripts/a.sh'); (p/'scripts').mkdir(); f=p/'scripts/a.sh'; f.write_text('echo synthetic'); f.chmod(0o644)
        self.assertEqual(self.kinds(), {'script-not-executable':1})
    def test_script_shebang(self):
        p=self.skill(body=BODY+'scripts/a.sh'); (p/'scripts').mkdir(); f=p/'scripts/a.sh'; f.write_text('#!/bin/sh\n'); f.chmod(0o644)
        self.assertEqual(self.report()['exit_code'],0)
    def test_script_exec(self):
        p=self.skill(body=BODY+'scripts/a.sh'); (p/'scripts').mkdir(); f=p/'scripts/a.sh'; f.touch(); f.chmod(0o755)
        self.assertEqual(self.report()['exit_code'],0)
    def test_skipped_tokens(self):
        self.skill(body=BODY+'`https://example.invalid/a.md` http://example.invalid/b.py /abs/a.md `scripts/*.sh`')
        self.assertEqual(self.report()['exit_code'],0)
    def test_root_fallback(self):
        self.skill(body=BODY+'docs/a.md'); (self.root/'docs').mkdir(); (self.root/'docs/a.md').touch()
        self.assertEqual(self.report()['exit_code'],0)
    def test_local_precedence(self):
        p=self.skill(body=BODY+'scripts/a.sh'); (p/'scripts').mkdir(); f=p/'scripts/a.sh'; f.write_text('#!/bin/sh'); f.chmod(0o644)
        (self.root/'scripts').mkdir(); f=self.root/'scripts/a.sh'; f.touch(); f.chmod(0o644)
        self.assertEqual(self.report()['exit_code'],0)
    def test_duplicate_names(self):
        self.skill(); self.skill('other',front='name: demo\ndescription: synthetic')
        self.assertEqual(self.kinds()['duplicate-skill-name'],2)
    def test_short_body(self):
        self.skill(body='short'); self.assertEqual(self.kinds(), {'empty-body':1})
    def test_body_boundary(self):
        self.skill(body='x'*50); self.assertEqual(self.report()['exit_code'],0)
    def test_ignore(self):
        self.skill(body=BODY+'scripts/missing.sh references/missing.md')
        r=self.report(ignore=['scripts/*','references/*']); self.assertEqual(r['ignored_count'],2); self.assertEqual(r['exit_code'],0)
    def test_dedup(self):
        self.skill(body=BODY+'scripts/a.sh `scripts/a.sh`'); self.assertEqual(self.kinds()['referenced-file'],1)
    def test_distinct_lines(self):
        self.skill(body=BODY+'scripts/a.sh\nscripts/a.sh'); self.assertEqual(self.kinds()['referenced-file'],2)
    def test_directory_claim(self):
        p=self.skill(body=BODY+'references/'); self.assertEqual(self.report()['exit_code'],2)
        (p/'references').mkdir(); self.assertEqual(self.report()['exit_code'],0)
    def test_directory_cannot_be_file(self):
        p=self.skill(body=BODY+'docs/'); (p/'docs').touch(); self.assertEqual(self.report()['exit_code'],2)
    def test_realistic(self):
        self.skill(front='name: old\ndescription: synthetic',body=BODY+'`scripts/old.py` `references/old.md`')
        self.assertEqual(self.report()['totals']['severity'], {'HIGH':2,'MEDIUM':1}); self.assertEqual(self.report()['exit_code'],2)
    def test_cap(self):
        self.skill(body=BODY+'\n'+'\n'.join('docs/%s.md'%i for i in range(510)))
        r=self.report(); self.assertEqual(len(r['findings']),500); self.assertEqual(r['omitted_count'],10); self.assertTrue(r['truncated']); self.assertEqual(r['totals']['kind']['referenced-file'],510)
    def test_order(self):
        self.skill('z',body=BODY+'docs/z.md'); self.skill('a',body=BODY+'docs/a.md')
        self.assertEqual([f['skill'] for f in self.report()['findings']], ['a','z'])
    def test_body_line(self):
        self.skill(body=BODY+'docs/a.md'); self.assertEqual(self.report()['findings'][0]['line'],5)
