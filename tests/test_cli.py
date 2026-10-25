import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from skill_drift.cli import main

class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
    def run_cli(self,*args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): code=main(list(args))
        return code,output.getvalue()
    def write(self,front='name: demo\ndescription: synthetic',body='Synthetic instructions for a local fixture with sufficient detail.'):
        p=self.root/'demo'; p.mkdir(exist_ok=True); (p/'SKILL.md').write_text('---\n'+front+'\n---\n'+body)
    def test_no_skills(self):
        code,out=self.run_cli('audit',str(self.root)); self.assertEqual(code,0); self.assertIn('no skills found',out)
    def test_good(self):
        self.write(); self.assertEqual(self.run_cli('audit',str(self.root))[0],0)
    def test_high(self):
        self.write(front='name: demo'); self.assertEqual(self.run_cli('audit',str(self.root))[0],2)
    def test_warn(self):
        self.write(front='name: old\ndescription: synthetic'); self.assertEqual(self.run_cli('audit',str(self.root))[0],1)
    def test_medium_threshold(self):
        self.write(front='name: old\ndescription: synthetic'); self.assertEqual(self.run_cli('audit',str(self.root),'--fail-on','medium')[0],2)
    def test_json(self):
        self.write(); code,out=self.run_cli('audit',str(self.root),'--json'); r=json.loads(out); self.assertEqual(code,r['exit_code']); self.assertEqual(r['verdict'],'PASS')
    def test_parse_error(self):
        self.write(front='name: demo\ndescription: |'); code,out=self.run_cli('audit',str(self.root),'--json'); self.assertEqual(code,2); self.assertEqual(json.loads(out)['parse_error_count'],1)
    def test_missing_path(self):
        code,out=self.run_cli('audit',str(self.root/'missing'),'--json'); self.assertEqual(code,2); self.assertEqual(json.loads(out)['parse_error_count'],1)
    def test_repeat_ignore(self):
        self.write(body='Synthetic instructions with adequate detail. scripts/a.sh docs/a.md')
        code,out=self.run_cli('audit',str(self.root),'--ignore','scripts/*','--ignore','docs/*','--json'); self.assertEqual(code,0); self.assertEqual(json.loads(out)['ignored_count'],2)
    def test_version(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm: main(['--version'])
        self.assertEqual(cm.exception.code,0); self.assertIn('0.1.0',out.getvalue())
    def test_help(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm: main(['--help'])
        self.assertEqual(cm.exception.code,0)
    def test_missing_frontmatter(self):
        self.write(); (self.root/'demo/SKILL.md').write_text('Synthetic instructions with enough characters to pass body length.')
        code,out=self.run_cli('audit',str(self.root)); self.assertEqual(code,2); self.assertIn('HIGH missing-frontmatter',out)
    def test_missing_reference(self):
        self.write(body='Synthetic instructions with enough detail. scripts/missing.sh')
        self.assertEqual(self.run_cli('audit',str(self.root))[0],2)
