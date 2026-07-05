import unittest

from scripts.retrieval import diversify_results


class DiversificationTests(unittest.TestCase):
    def test_prefers_distinct_sections_and_suppresses_near_duplicates(self):
        rows=[
            {"id":"top","sectionKey":"part-i:item-1a","score":10.0,"text":"supply chain disruption creates material production risk"},
            {"id":"duplicate","sectionKey":"part-i:item-1a","score":9.0,"text":"supply chain disruption creates material production risk today"},
            {"id":"mda","sectionKey":"part-ii:item-7","score":3.0,"text":"liquidity and capital resources support operations"},
            {"id":"weak","sectionKey":"part-ii:item-8","score":2.0,"text":"financial statement accounting policy"},
        ]
        result=diversify_results(rows,3)
        self.assertEqual([row["id"] for row in result],["top","mda","weak"])

    def test_is_deterministic_and_preserves_scores(self):
        rows=[{"id":str(i),"item":f"Item {i}","score":5-i,"text":f"unique evidence passage number {i}"} for i in range(4)]
        self.assertEqual(diversify_results(rows,3),diversify_results(rows,3))
        self.assertEqual(diversify_results(rows,3)[0]["score"],5)


if __name__=="__main__": unittest.main()
