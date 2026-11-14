"""Checks that the review tool agrees with the official starter and workflow. Standard library only.

    python3 -I test_review_tool.py -v
"""
import collections, json, pathlib, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data_io import load_data  # noqa: E402
import review_tool, starter, workflow  # noqa: E402

ROUTE = '03-qc'


class ReviewToolChecks:
    fixture = None

    @classmethod
    def setUpClass(cls):
        cls.data = load_data(HERE / ROUTE, cls.fixture)
        cls.feats = review_tool.build(ROUTE, cls.data)
        cls.cases = [f for f in cls.feats if f['split'] == 'cases']

    def test_every_case_has_exactly_one_known_bucket(self):
        self.assertEqual(len(self.cases), len(self.data['cases']))
        self.assertEqual(len({f['id'] for f in self.cases}), len(self.cases))
        for f in self.cases:
            self.assertIn(f['bucket'], review_tool.BUCKETS)

    def test_bucket_counts_sum_to_cases(self):
        counts = collections.Counter(f['bucket'] for f in self.cases)
        self.assertEqual(sum(counts.values()), len(self.data['cases']))

    def test_decisions_match_starter(self):
        for model, key in (('baseline', 'ca_keep'), ('abundance', 'ab_keep')):
            official = {r['id']: r['keep'] for r in starter.run(ROUTE, self.data, model)['rows']}
            for f in self.cases:
                self.assertEqual(f[key], official[f['id']], (model, f['id']))

    def test_signal_totals_match_workflow_summary(self):
        submission = starter.run(ROUTE, self.data, 'baseline')
        with tempfile.TemporaryDirectory() as tmp:
            workflow.export(ROUTE, self.data, submission, pathlib.Path(tmp))
            summary = json.loads((pathlib.Path(tmp) / 'summary.json').read_text())['signal_mass']
        ours = review_tool.signal_summary(self.feats)
        self.assertEqual(set(ours), set(summary))
        for cohort, s in summary.items():
            self.assertAlmostEqual(ours[cohort]['ca_retained'], s['retained'], places=9)
            self.assertAlmostEqual(ours[cohort]['ca_removed'], s['removed'], places=9)

    def test_no_signal_bucket_is_zero_signal_kept_by_control_aware(self):
        for f in self.feats:
            if f['bucket'] == 'no_signal':
                self.assertEqual(f['sample_mass'], 0)
                self.assertTrue(f['ca_keep'])
                self.assertFalse(f['ab_keep'])

    def test_disagreement_buckets_really_disagree(self):
        for f in self.feats:
            if f['bucket'] in ('rare_recurring', 'rare_sparse', 'control_flagged'):
                self.assertNotEqual(f['ca_keep'], f['ab_keep'], f['id'])
            if f['bucket'] in ('agree_keep', 'agree_remove'):
                self.assertEqual(f['ca_keep'], f['ab_keep'], f['id'])


class FixtureChecks(ReviewToolChecks, unittest.TestCase):
    fixture = True


class FullDataChecks(ReviewToolChecks, unittest.TestCase):
    fixture = False

    def test_labeled_accuracy_is_computed_on_all_labeled_rows(self):
        acc = review_tool.labeled_accuracy(self.feats)
        self.assertEqual(acc['all']['n'], len(self.data['train']))
        self.assertEqual(acc['all']['real'], sum(bool(r['target']) for r in self.data['train']))
        self.assertEqual(sum(v['n'] for k, v in acc.items() if k != 'all'), acc['all']['n'])

    def test_report_embeds_data_and_renders_without_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'report.html'
            sys.argv = ['review_tool.py', '--output', str(out)]
            review_tool.main()
            html = out.read_text()
        self.assertNotIn('/*__DATA__*/null', html)
        self.assertIn('"rare_recurring"', html)


if __name__ == '__main__':
    unittest.main()
