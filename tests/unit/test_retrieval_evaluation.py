import unittest

from petcare.vision.retrieval_evaluation import (
    RetrievalEvaluationError,
    evaluate_rankings,
)


class RetrievalEvaluationTests(unittest.TestCase):
    def test_precision_recall_and_reciprocal_rank_use_external_labels(self):
        metrics = evaluate_rankings(
            {"q1": ["a", "b", "c"], "q2": ["x", "y", "z"]},
            {"q1": {"b"}, "q2": {"missing"}},
            k=2,
        )
        self.assertEqual(metrics.queries, 2)
        self.assertEqual(metrics.precision_at_k, 0.25)
        self.assertEqual(metrics.recall_at_k, 0.5)
        self.assertEqual(metrics.mean_reciprocal_rank, 0.25)

    def test_rejects_unpaired_labels_duplicate_ids_and_bad_k(self):
        invalid = (
            ({"q": ["a"]}, {}, 1),
            ({"q": ["a", "a"]}, {"q": {"a"}}, 1),
            ({"q": ["a"]}, {"q": {"a"}}, 0),
            ({"q": ["a"]}, {"q": set()}, 1),
        )
        for rankings, labels, k in invalid:
            with self.subTest(rankings=rankings, labels=labels, k=k):
                with self.assertRaises(RetrievalEvaluationError):
                    evaluate_rankings(rankings, labels, k=k)


if __name__ == "__main__":
    unittest.main()
