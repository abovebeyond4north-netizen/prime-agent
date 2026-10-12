import unittest
from research.changing_policy import ThresholdMemory, run_study


class ChangingPolicyTests(unittest.TestCase):
    def test_revision_recovers_after_shift_and_return(self):
        report = run_study()
        self.assertTrue(report['reference_acceptance'])
        self.assertFalse(report['automatic_promotion'])
        for trial in report['trials']:
            adaptive = [r for r in trial['rows'] if r['mode'] == 'revising']
            self.assertTrue(all(r['correct'] == r['total'] for r in adaptive))
            self.assertGreater(adaptive[-1]['state']['resets'], 0)
            frozen = [r for r in trial['rows'] if r['mode'] == 'frozen']
            self.assertLess(frozen[1]['correct'], frozen[1]['total'])

    def test_test_predictions_do_not_update_memory(self):
        learner = ThresholdMemory('revising')
        learner.observe(3, 0)
        before = learner.state()
        restored = ThresholdMemory.restore(before)
        for x in (0.5, 3.5, 15.5):
            self.assertEqual(learner.predict(x), restored.predict(x))
        self.assertEqual(before, learner.state())

    def test_duplicate_schedules_rejected(self):
        with self.assertRaises(ValueError):
            run_study((1, 1, 2))
