"""CMD-GR4 (U1, worker side of rlo CMD-K11 in-turn ReAct): the substitutes map, the worker rule, doctor's checks.

The replays of W1's four cases against K11 rlo (S3) wait for K11 to land; these tests cover what exists now.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ga_rlo import remote

from world import run_cli


class SubstitutesTest(unittest.TestCase):
    def test_the_map_serves_plumbing_only(self):
        self.assertEqual(remote.SUBSTITUTES, {"ReadNotifications": ["mcp__github__issue_read"]})
        for t in ("WebFetch", "Agent", "mcp__claude-code-remote__create_session"):
            self.assertNotIn(t, remote.SUBSTITUTES)
        self.assertEqual(remote.substitute_problems(remote.model("W", substitutes=True)), [])

    def test_mutations_on_the_map_are_caught(self):
        good = remote.model("W", substitutes=True)
        cases = {
            "a substitute for WebFetch": {"WebFetch": ["mcp__github__issue_read"]},
            "a substitute outside the model": {"ReadNotifications": ["mcp__github__get_file_contents"]},
            "an ungranted external substitute": {"ReadNotifications": ["mcp__github__create_issue"]},
        }
        for what, subs in cases.items():
            with self.subTest(what=what):
                m = json.loads(json.dumps(good))
                if what == "an ungranted external substitute":
                    m["specs"].append(dict(m["specs"][0], name="mcp__github__create_issue", risk="external"))
                m["substitutes"] = subs
                self.assertTrue(remote.substitute_problems(m), what)

    def test_written_only_when_the_installed_rlo_reads_it(self):
        """rlo 0.5.1 rejects an action-model with 'substitutes': writing it would deny every call (fail closed)."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        remote.write(d, "W1")
        m = json.loads((d / "ops/rlo/model.json").read_text())
        self.assertEqual("substitutes" in m, remote.substitutes_supported())
        if not remote.substitutes_supported():
            m["substitutes"] = remote.SUBSTITUTES
            (d / "ops/rlo/model.json").write_text(json.dumps(m))
            self.assertTrue(any("cannot read" in p for p in remote.problems(d)))


class WorkerRuleTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.assertEqual(run_cli("init", "--profile", "remote", "--work-repo", str(self.repo), "--name", "W1")[0], 0)

    def test_rule_in_guard_md_and_prompt(self):
        for f in ("GUARD.md", "PROMPT.md"):
            text = (self.repo / "ops/rlo" / f).read_text()
            self.assertIn(remote.REACT_RULE, text)
            self.assertIn("-- react:", text)
            self.assertIn("escalate is true", text)
            self.assertIn(remote.DENY_REPORT, text)  # a deny without a react line (older rlo) is still reported
        self.assertEqual(remote.problems(self.repo), [])

    def test_rule_removed_or_escalate_dropped_is_caught(self):
        for f in ("GUARD.md", "PROMPT.md"):
            for cut in (remote.REACT_RULE, "When escalate is true, post the deny verbatim on your channel and continue "
                                           "other work."):
                with self.subTest(f=f, cut=cut[:20]):
                    p = self.repo / "ops/rlo" / f
                    good = p.read_text()
                    p.write_text(good.replace(cut, ""))
                    self.assertTrue(any("ReAct rule" in x for x in remote.problems(self.repo)))
                    p.write_text(good)


if __name__ == "__main__":
    unittest.main()
