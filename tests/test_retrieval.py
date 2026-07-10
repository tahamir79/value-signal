import unittest

from scripts.build_search_index import bm25_search,build_index,tokenize
from scripts.chunk_filings import chunk_filing
from scripts.providers.sec_filings import FilingDocument
from scripts.text_cleaning import clean_filing_html
from scripts.build_universe import build_universe


def filing(form="10-K"):
    return FilingDocument("TEST","0000000001","0000000001-26-000001","2026-02-01","2025-12-31",form,"test.htm","https://www.sec.gov/Archives/edgar/data/1/000000000126000001/test.htm","")


class RetrievalTests(unittest.TestCase):
    def test_universe_exposes_company_name_for_chunk_metadata(self):
        security=build_universe(1)[0]
        self.assertEqual(security.company_name,"Apple Inc.")

    def test_cleaner_removes_markup_scripts_and_repeated_headers(self):
        source="<html><script>secret()</script><body>"+("<p>ACME 2025 FORM 10-K</p>"*4)+"<h2>Item 1A. Risk Factors</h2><p>Supply chain disruption could interrupt production.</p></body></html>"
        cleaned=clean_filing_html(source)
        self.assertNotIn("secret",cleaned); self.assertNotIn("<p>",cleaned); self.assertNotIn("ACME 2025",cleaned)
        self.assertIn("Supply chain disruption",cleaned)

    def test_metadata_survives_chunking_and_empty_chunks_are_removed(self):
        text="Item 1A. Risk Factors\n"+"Cybersecurity incidents may disrupt operations and expose customer information. "*35
        chunks=chunk_filing(filing(),text,target_words=80,overlap_words=15,minimum_words=20)
        self.assertGreater(len(chunks),1)
        for chunk in chunks:
            self.assertEqual(chunk["accession"],filing().accession); self.assertEqual(chunk["form"],"10-K")
            self.assertEqual(chunk["item"],"Item 1A. Risk Factors"); self.assertTrue(chunk["url"].startswith("https://www.sec.gov/Archives/")); self.assertTrue(chunk["text"].strip())

    def test_bm25_ranks_relevant_passage_and_traces_terms(self):
        base={"ticker":"TEST","accession":"a","filingDate":"2026-01-01","reportDate":"2025-12-31","form":"10-K","url":"https://www.sec.gov/a","wordStart":0,"wordEnd":30}
        chunks=[{**base,"id":"risk","item":"Item 1A","text":"Supply chain concentration and sole source suppliers may disrupt production and increase costs."},{**base,"id":"other","item":"Item 7","text":"Revenue increased due to product demand and foreign currency movements."}]
        index=build_index(chunks)
        results=bm25_search(index,"supplier supply chain risk",ticker="TEST")
        self.assertEqual(results[0]["id"],"risk"); self.assertIn("supply",results[0]["matchedTerms"]); self.assertGreater(results[0]["score"],0)
        self.assertIn("supplier",tokenize("The supplier and the supply chain"))

    def test_ticker_filter_and_complete_citation(self):
        base={"accession":"a","filingDate":"2026-01-01","reportDate":"2025-12-31","form":"10-Q","item":"Item 1A","text":"Liquidity risk and debt maturity risk.","url":"https://www.sec.gov/Archives/example","wordStart":0,"wordEnd":10}
        index=build_index([{**base,"id":"a","ticker":"AAA"},{**base,"id":"b","ticker":"BBB"}])
        results=bm25_search(index,"liquidity risk",ticker="BBB")
        self.assertEqual([row["ticker"] for row in results],["BBB"]); self.assertEqual(results[0]["url"],base["url"])

    def test_part_aware_sections_do_not_cross_boundaries_and_offsets_reconstruct(self):
        text=("Part I\n\nItem 1. Financial Statements\n\n"+
              "First part financial statement discussion has enough substantive words to remain searchable. "*6+
              "\n\nPart II\n\nItem 1. Legal Proceedings\n\nNone.")
        chunks=chunk_filing(filing("10-Q"),text)
        self.assertEqual([row["sectionKey"] for row in chunks],["part-i:item-1","part-ii:item-1"])
        self.assertNotIn("Part II",chunks[0]["text"])
        for chunk in chunks:
            self.assertEqual(text[chunk["documentCharStart"]:chunk["documentCharEnd"]],chunk["text"])

    def test_stable_ids_links_and_schema(self):
        text="Part I\n\nItem 1A. Risk Factors\n\n"+("Operational demand and margin risks may affect results. "*90)
        first=chunk_filing(filing(),text)
        second=chunk_filing(filing(),"Unrelated preface.\n\n"+text)
        self.assertEqual([row["chunkId"] for row in first],[row["chunkId"] for row in second])
        self.assertTrue(all(row["schemaVersion"]=="3.0.0" for row in first))
        for index,row in enumerate(first):
            self.assertEqual(row["previousChunkId"],first[index-1]["chunkId"] if index else None)
            self.assertEqual(row["nextChunkId"],first[index+1]["chunkId"] if index+1<len(first) else None)

    def test_table_cells_remain_in_source_order(self):
        cleaned=clean_filing_html("<table><tr><th>Year</th><th>Revenue</th></tr><tr><td>2025</td><td>100</td></tr></table>")
        self.assertLess(cleaned.index("Year"),cleaned.index("Revenue"))
        self.assertLess(cleaned.index("Revenue"),cleaned.index("2025"))
        self.assertLess(cleaned.index("2025"),cleaned.index("100"))

    def test_duplicate_toc_heading_prefers_substantive_body(self):
        text=("Part I\nItem 1. Business\nItem 1A. Risk Factors\n\n"
              "Part I\nItem 1. Business\n"+("Substantive operations and customer discussion. "*70)+
              "\nItem 1A. Risk Factors\n"+("Material supplier concentration risk. "*70))
        chunks=chunk_filing(filing(),text)
        self.assertEqual({row["sectionKey"] for row in chunks},{"part-i:item-1","part-i:item-1a"})
        self.assertTrue(all("Substantive" in row["text"] or "supplier" in row["text"] for row in chunks))

    def test_oversized_sentence_uses_fixed_windows_with_exact_offsets(self):
        sentence=" ".join(f"token{index}" for index in range(520))+"."
        text="Part I\nItem 1A. Risk Factors\n"+sentence
        chunks=chunk_filing(filing(),text)
        self.assertGreaterEqual(len(chunks),2)
        self.assertTrue(all(row["boundaryType"]=="fixed_window_fallback" for row in chunks))
        self.assertTrue(all(len(row["text"].split())<=300 for row in chunks))
        for row in chunks:
            self.assertEqual(text[row["documentCharStart"]:row["documentCharEnd"]],row["text"])

    def test_short_sections_survive_reserved_sections_do_not_and_tails_merge(self):
        short=chunk_filing(filing(),"Part II\nItem 1. Legal Proceedings\nNone.\nItem 2. Reserved\nReserved")
        self.assertEqual(len(short),1); self.assertEqual(short[0]["boundaryType"],"short_section")
        body=("core "*300).strip()+"\n"+("tail "*10).strip()
        merged=chunk_filing(filing(),"Part II\nItem 7. Management Discussion\n"+body)
        self.assertEqual(len(merged),1); self.assertEqual(merged[0]["boundaryType"],"merged_tail")

    def test_only_substantive_labeled_preamble_is_searchable(self):
        text=("Cover page\nForward-Looking Statements\n"+("Expectations involve uncertainty and assumptions. "*25)+
              "\nPart I\nItem 1. Business\n"+("Business operations description. "*40))
        chunks=chunk_filing(filing(),text)
        self.assertIn("preamble:forward-looking-statements",{row["sectionKey"] for row in chunks})
        self.assertFalse(any(row["sectionTitle"]=="Cover page" for row in chunks))
        contaminated=("Forward-Looking Statements\n"+("Cautious uncertainty language. "*40)+
                      "\nItem 99. Navigation Noise\n"+("Unrelated payload. "*200)+
                      "\nPart I\nItem 1. Business\n"+("Business description. "*40))
        preamble=[row for row in chunk_filing(filing(),contaminated) if row["sectionKey"]=="preamble:forward-looking-statements"]
        self.assertTrue(preamble); self.assertFalse(any("Unrelated payload" in row["text"] for row in preamble))

    def test_terminal_signatures_do_not_enter_item_16(self):
        text=("Part IV\nItem 15. Exhibits\n"+("Exhibit description. "*40)+
              "\nItem 16. Form 10-K Summary\nNone.\nSIGNATURES\n"+("Director signature block. "*200))
        chunks=chunk_filing(filing(),text)
        item16=[row for row in chunks if row["sectionKey"]=="part-iv:item-16"]
        self.assertEqual(len(item16),1); self.assertEqual(item16[0]["text"],"None.")
        self.assertFalse(any("signature" in row["text"].lower() for row in chunks))
        oversized=("Part I\nItem 1. Business\n"+("Business evidence. "*100)+
                   "\nPart IV\nItem 16. Form 10-K Summary\n"+("Implausible summary payload. "*1200))
        self.assertNotIn("part-iv:item-16",{row["sectionKey"] for row in chunk_filing(filing(),oversized)})

    def test_overlap_is_exactly_last_sentence_not_whole_paragraph(self):
        first=("Alpha evidence remains relevant for valuation analysis and operating context. "*4)+"Final bridge sentence."
        second="New paragraph discusses liquidity debt maturities and cash resources. "*5
        chunks=chunk_filing(filing(),f"Part I\nItem 1. Business\n{first}\n{second}",target_words=30,overlap_words=60)
        self.assertGreaterEqual(len(chunks),2)
        self.assertTrue(chunks[1]["text"].startswith("Final bridge sentence."))
        self.assertNotIn("Alpha evidence",chunks[1]["text"])

    def test_rejected_item_heading_still_ends_prior_section(self):
        text=("Part I\nItem 1. Financial Statements\n"+("Financial statement evidence. "*50)+
              "\nPart II\nItem 1A. Risk Factors\n"+("Risk evidence. "*40)+
              "\nItem 99. Invalid Navigation\n"+("Unrelated payload. "*300))
        risk=[row for row in chunk_filing(filing("10-Q"),text) if row["sectionKey"]=="part-ii:item-1a"]
        self.assertTrue(risk); self.assertFalse(any("Unrelated payload" in row["text"] for row in risk))

    def test_dominant_section_fails_closed(self):
        text=("Part I\nItem 1. Business\n"+("Oversized malformed business payload. "*1500)+
              "\nItem 1A. Risk Factors\nA short but meaningful risk statement.")
        keys={row["sectionKey"] for row in chunk_filing(filing(),text)}
        self.assertNotIn("part-i:item-1",keys); self.assertIn("part-i:item-1a",keys)


if __name__=="__main__": unittest.main()
