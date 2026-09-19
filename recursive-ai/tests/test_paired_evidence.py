import unittest

from research.paired_evidence import paired_resource_evidence


def rows(n, attempts=10):
    return [dict(seed=i, goal="test", goal_reached=True, audit_passed=True,
                 coverage=1.0, attempts=attempts, container_runs=20, model_calls=0)
            for i in range(n)]


class PairedEvidenceTests(unittest.TestCase):
    def test_one_pair_is_not_proof(self):
        report = paired_resource_evidence(rows(1, 9), rows(1))
        self.assertEqual(report["status"], "gain_not_established")
        self.assertEqual(report["metrics"]["attempts"]["one_sided_sign_p"], 0.5)

    def test_exact_probability_and_multiple_comparison_correction(self):
        report = paired_resource_evidence(rows(6, 9), rows(6))
        self.assertEqual(report["metrics"]["attempts"]["holm_adjusted_p"], 3 / 64)
        self.assertEqual(report["status"], "supported_directional_resource_gain")
        self.assertFalse(report["automatic_promotion"])

    def test_ties_and_reordered_pairs(self):
        self.assertEqual(paired_resource_evidence(rows(8), rows(8)),
                         paired_resource_evidence(rows(8)[::-1], rows(8)))
        self.assertEqual(paired_resource_evidence(rows(8), rows(8))["status"], "gain_not_established")

    def test_failure_cannot_look_like_efficiency(self):
        for field, value in (("audit_passed", False), ("goal_reached", False),
                             ("coverage", 0.5), ("container_runs", 21)):
            candidate = rows(8, 1)
            candidate[0][field] = value
            self.assertEqual(paired_resource_evidence(candidate, rows(8))["status"], "gain_not_established")

    def test_missing_duplicate_and_malformed_evidence(self):
        bad_cases = [[], rows(2) + rows(1), rows(1), rows(2)]
        bad_cases[-1][0]["attempts"] = float("nan")
        for candidate in bad_cases:
            with self.assertRaises(ValueError):
                paired_resource_evidence(candidate, rows(2))
        for value in (True, -1, 1.5, float("inf")):
            candidate = rows(2)
            candidate[0]["model_calls"] = value
            with self.assertRaises(ValueError):
                paired_resource_evidence(candidate, rows(2))

    def test_mixed_signs_do_not_support_gain(self):
        candidate = rows(8, 9)
        for row in candidate[4:]:
            row["attempts"] = 11
        report = paired_resource_evidence(candidate, rows(8))
        self.assertEqual(report["status"], "gain_not_established")
        self.assertAlmostEqual(report["metrics"]["attempts"]["one_sided_sign_p"], 163 / 256)


if __name__ == "__main__":
    unittest.main()
