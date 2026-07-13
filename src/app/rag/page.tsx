import {LocalRagConsole} from "@/components/LocalRagConsole";
import { isLocalRagEnabled } from "@/lib/rag-availability";

export const dynamic="force-dynamic";

export default function RagPage(){
  if(!isLocalRagEnabled()){
    return <main className="page rag-page"><section className="page-head"><p className="eyebrow">RAG / ONLINE PREVIEW</p><h1>RAG will be available online in the near future.</h1><p>The public deployment keeps the retrieval/search experience available while the Llama synthesis console remains local-only. This protects the live site from calling a laptop Ollama service or exposing experimental AI behavior before it is production-ready.</p></section><section className="rag-placeholder"><p className="eyebrow">WHAT IS READY NOW</p><h2>Use the stock pages for cited SEC evidence.</h2><p>Company pages still show deterministic ValueSignal scores, balance-sheet-aware risk context, analyst briefs, and BM25 filing evidence. The future online RAG layer will summarize and challenge those signals with cited evidence, without giving buy/sell/hold advice.</p></section></main>;
  }
  return <main className="page rag-page"><section className="page-head"><p className="eyebrow">LOCAL RAG LAB</p><h1>Llama filing research console</h1><p>Ask local-only questions against the SEC filing retrieval index. This lab calls your local Python RAG pipeline and Ollama; it is research support, not financial advice or a recommendation engine.</p></section><LocalRagConsole /></main>;
}
