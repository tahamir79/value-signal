import {LocalRagConsole} from "@/components/LocalRagConsole";

export const dynamic="force-dynamic";

export default function RagPage(){
  return <main className="page rag-page"><section className="page-head"><p className="eyebrow">LOCAL RAG LAB</p><h1>Llama filing research console</h1><p>Ask local-only questions against the SEC filing retrieval index. This lab calls your local Python RAG pipeline and Ollama; it is research support, not financial advice or a recommendation engine.</p></section><LocalRagConsole /></main>;
}
