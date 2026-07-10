import os
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from rag.config import RagConfig
from rag.embedding_retriever import cosine_similarity, embedding_search
from rag.embedding_store import StaleEmbeddingStore, load_store, make_store, save_store
from rag.ollama_client import OllamaError, check_model_available, generate_with_llama, get_embedding
from scripts.build_rag_embeddings import build_embeddings


class ConfigTests(unittest.TestCase):
    def test_environment_configuration_and_validation(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL":"http://x/", "RAG_TOP_K":"4", "RAG_MAX_CONTEXT_CHARS":"7000"}, clear=True):
            config=RagConfig.from_env()
            self.assertEqual(config.ollama_base_url,"http://x"); self.assertEqual(config.top_k,4)
        with patch.dict(os.environ,{"RAG_TOP_K":"0"},clear=True):
            with self.assertRaisesRegex(ValueError,"greater than zero"): RagConfig.from_env()


class ClientTests(unittest.TestCase):
    @patch("rag.ollama_client._request")
    def test_model_alias_embedding_and_generation(self, request):
        request.side_effect=[{"models":[{"name":"nomic-embed-text:latest"}]},{"embeddings":[[1,2]]},
                             {"models":[{"name":"llama3.2:3b"}]},{"response":" grounded "}]
        self.assertEqual(get_embedding("text"),[1.0,2.0])
        self.assertEqual(generate_with_llama("prompt"),"grounded")

    @patch("rag.ollama_client._request", return_value={"models":[]})
    def test_missing_model_has_pull_instruction(self, _request):
        with self.assertRaisesRegex(OllamaError,"ollama pull nomic-embed-text"): get_embedding("x")

    @patch("rag.ollama_client.urlopen", side_effect=URLError("down"))
    def test_connection_error_is_clear(self, _open):
        from rag.ollama_client import _request
        with self.assertRaisesRegex(OllamaError,"Ollama is not running"): _request("/api/tags")


class StoreAndRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.chunks=[{"chunkId":"a","ticker":"AAA","form":"10-K","text":"alpha"},
                     {"chunkId":"b","ticker":"BBB","form":"10-Q","text":"beta"}]
        self.store=make_store("hash","model",self.chunks,[[1,0],[0,1]],"v1")

    def test_round_trip_and_strict_cache_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"vectors.json"; save_store(path,self.store); loaded=load_store(path)
            loaded.validate(corpus_hash="hash",model="model",chunks=self.chunks)
            with self.assertRaisesRegex(StaleEmbeddingStore,"ordering changed"):
                loaded.validate(corpus_hash="hash",model="model",chunks=list(reversed(self.chunks)))
            with self.assertRaisesRegex(StaleEmbeddingStore,"corpus hash changed"):
                loaded.validate(corpus_hash="new",model="model",chunks=self.chunks)

    def test_cosine_ranking_and_filters(self):
        self.assertAlmostEqual(cosine_similarity([1,0],[1,0]),1)
        results=embedding_search(self.store,self.chunks,"query",embed=lambda _:[0,1],ticker="BBB",form_type="10-Q")
        self.assertEqual([row["chunkId"] for row in results],["b"]); self.assertEqual(results[0]["embeddingScore"],1)

    def test_dimension_mismatch_is_explicit(self):
        with self.assertRaisesRegex(ValueError,"dimensions differ"):
            embedding_search(self.store,self.chunks,"query",embed=lambda _:[1])

    @patch("scripts.build_rag_embeddings.get_embeddings", side_effect=lambda texts, model:[[1.0,0.0] for _ in texts])
    def test_embedding_builder_caches_and_reuses_vectors(self, embed):
        with tempfile.TemporaryDirectory() as folder:
            index_path=Path(folder)/"index.json"; cache=Path(folder)/"vectors.json"
            index_path.write_text(json.dumps({"corpusHash":"hash","documents":self.chunks}),encoding="utf-8")
            self.assertIn("Built 2",build_embeddings(index_path,cache,batch_size=1)); self.assertEqual(embed.call_count,2)
            self.assertIn("reused",build_embeddings(index_path,cache,batch_size=1)); self.assertEqual(embed.call_count,2)


if __name__ == "__main__": unittest.main()
