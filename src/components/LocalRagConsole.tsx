"use client";

import {useState,type FormEvent} from "react";

type RagChunk={chunkId?:string;id?:string;ticker?:string;companyName?:string;formType?:string;form?:string;sectionKey?:string;sectionTitle?:string;filingDate?:string;text?:string;score?:number;sourceUrl?:string;url?:string;matchedTerms?:string[];retrievalIntent?:string};
type RagResult={answer?:string|null;limitations?:string|null;warnings?:string[];citations?:string[];retrieved_chunks?:RagChunk[];retrieval_mode?:string;intent?:string;synthesis_depth?:string;error?:string;official_signal?:string;official_signal_label?:string;signal_confidence?:string;evidence_assessment?:string;evidence_relevance?:string;signal_relationship?:string;deterministic_risk_posture?:string;stock_context?:{scores?:Record<string,number|null>;rawFeatures?:Record<string,number|null>;missingFeatures?:string[]}};
type ChatMessage={id:string;role:"user"|"assistant";ticker:string;query?:string;content:string;result?:RagResult};

const suggested=[
  {ticker:"AAPL",query:"What are the most important product and supply chain risks?"},
  {ticker:"MSFT",query:"Further review of Microsoft's cybersecurity risk management practices, including details on specific mitigation strategies and their impact on the company"},
  {ticker:"F",query:"Is the signal strong enough?"},
  {ticker:"JPM",query:"What does management say about credit and market risk?"},
];

function messageId(){return `${Date.now()}-${Math.random().toString(16).slice(2)}`;}

function answerText(result:RagResult){
  if(result.error)return result.error;
  return result.answer??result.limitations??"I found cited SEC filing evidence, but local Llama did not return a synthesis. Review the retrieved passages below.";
}

function sessionSummary(messages:ChatMessage[],ticker:string){
  const prior=messages.filter(message=>message.ticker===ticker&&message.role==="assistant"&&message.result&&!message.result.error).slice(-3);
  if(!prior.length)return "";
  return prior.map(message=>{
    const chunks=(message.result?.citations??[]).slice(0,4).join(", ")||"none";
    return `Prior intent: ${message.result?.intent??"general"}; question: ${message.query??"unknown"}; themes: ${message.result?.evidence_relevance??message.result?.evidence_assessment??"unknown"} / ${message.result?.signal_relationship??"unknown"}; previous chunk IDs: ${chunks}.`;
  }).join("\n");
}

export function LocalRagConsole(){
  const [ticker,setTicker]=useState("AAPL");
  const [query,setQuery]=useState("What are the key risk factors?");
  const [mode,setMode]=useState("hybrid");
  const [depth,setDepth]=useState<"quick"|"deep">("deep");
  const [topK,setTopK]=useState(6);
  const [synthesize,setSynthesize]=useState(true);
  const [loading,setLoading]=useState(false);
  const [messages,setMessages]=useState<ChatMessage[]>([
    {id:"welcome",role:"assistant",ticker:"VS",content:"Ask me a cautious research question about a stock. I will retrieve SEC filing evidence and, when Ollama is running, use local Llama to synthesize an answer with caveats."},
  ]);

  async function ask(event?:FormEvent,override?:{ticker:string;query:string}){
    event?.preventDefault();
    const nextTicker=(override?.ticker??ticker).trim().toUpperCase();
    const nextQuery=(override?.query??query).trim();
    if(nextQuery.length<3||loading)return;
    const nextTopK=depth==="deep"?Math.max(topK,6):Math.min(topK,3);
    const priorSummary=sessionSummary(messages,nextTicker);
    setTicker(nextTicker);
    setQuery("");
    const userMessage:ChatMessage={id:messageId(),role:"user",ticker:nextTicker,query:nextQuery,content:nextQuery};
    setMessages(current=>[...current,userMessage]);
    setLoading(true);
    try{
      const response=await fetch("/api/rag",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ticker:nextTicker,query:nextQuery,mode,topK:nextTopK,depth,sessionSummary:priorSummary,synthesize})});
      const payload=await response.json() as RagResult;
      const result=response.ok?payload:{error:payload.error??"RAG request failed."};
      setMessages(current=>[...current,{id:messageId(),role:"assistant",ticker:nextTicker,query:nextQuery,content:answerText(result),result}]);
    }catch(error){
      const result={error:error instanceof Error?error.message:String(error)};
      setMessages(current=>[...current,{id:messageId(),role:"assistant",ticker:nextTicker,query:nextQuery,content:answerText(result),result}]);
    }finally{
      setLoading(false);
    }
  }

  return <section className="rag-console"><div className="local-only-note"><strong>Local only.</strong><span>Deep mode uses local Ollama for longer analyst-style answers. Responses are research support only, never buy/sell/hold instructions.</span></div><div className="rag-chat-layout"><aside className="rag-settings" aria-label="Local RAG settings"><label><span>Ticker</span><input value={ticker} onChange={event=>setTicker(event.target.value.toUpperCase())} maxLength={10}/></label><label><span>Retrieval mode</span><select value={mode} onChange={event=>setMode(event.target.value)}><option value="hybrid">Hybrid</option><option value="bm25">BM25 only</option><option value="embedding">Embedding only</option></select></label><label><span>Synthesis depth</span><select value={depth} onChange={event=>setDepth(event.target.value==="quick"?"quick":"deep")}><option value="deep">Deep research</option><option value="quick">Quick</option></select></label><label><span>Evidence count</span><input type="number" min={1} max={8} value={topK} onChange={event=>setTopK(Number(event.target.value))}/></label><label className="rag-toggle"><input type="checkbox" checked={synthesize} onChange={event=>setSynthesize(event.target.checked)}/><span>Synthesize with local Llama</span></label><button type="button" onClick={()=>setMessages(messages.slice(0,1))}>Clear chat</button></aside><div className="rag-chat"><div className="rag-thread" aria-live="polite">{messages.map(message=><article className={`chat-message chat-${message.role}`} key={message.id}><header><strong>{message.role==="user"?"You":"Local Llama / RAG"}</strong><span>{message.ticker}{message.result?.intent?` · ${message.result.intent}`:""}{message.result?.synthesis_depth?` · ${message.result.synthesis_depth}`:""}{message.result?.retrieval_mode?` · ${message.result.retrieval_mode}`:""}</span></header>{message.result&&!message.result.error&&<dl className="rag-signal-context"><div><dt>Official signal</dt><dd>{message.result.official_signal_label??"Not available"}</dd></div><div><dt>Evidence relevance</dt><dd>{message.result.evidence_relevance??"Insufficient evidence"}</dd></div><div><dt>Signal relationship</dt><dd>{message.result.signal_relationship??message.result.evidence_assessment??"Not enough evidence"}</dd></div></dl>}<p>{message.content}</p>{message.result?.error&&<div className="rag-error compact"><strong>RAG unavailable</strong><p>Check that Ollama is running, then try `ollama pull llama3.2:3b` and `ollama pull nomic-embed-text` if needed.</p></div>}{Boolean(message.result?.warnings?.length)&&<div className="rag-warnings compact"><strong>Warnings</strong><ul>{message.result?.warnings?.map(warning=><li key={warning}>{warning}</li>)}</ul></div>}{Boolean(message.result?.stock_context?.scores)&&<details className="chat-evidence"><summary>Pipeline scores and raw features</summary><p>Scores: {Object.entries(message.result?.stock_context?.scores??{}).map(([key,value])=>`${key}=${value}`).join(", ")||"Not available"}</p><p>Raw features: {Object.entries(message.result?.stock_context?.rawFeatures??{}).map(([key,value])=>`${key}=${value}`).join(", ")||"Not available"}</p></details>}{Boolean(message.result?.retrieved_chunks?.length)&&<details className="chat-evidence"><summary>{message.result?.retrieved_chunks?.length} cited evidence passage{message.result?.retrieved_chunks?.length===1?"":"s"}</summary><div className="evidence-results">{message.result?.retrieved_chunks?.map(chunk=>{const source=chunk.sourceUrl??chunk.url;return <article key={chunk.chunkId??chunk.id}><header><div><strong>{chunk.ticker??message.ticker} · {chunk.formType??chunk.form??"Filing"} · {chunk.sectionKey??"section"}</strong><span>{chunk.sectionTitle??"Section title unavailable"} · Filed {chunk.filingDate??"unknown"}</span></div><b>{typeof chunk.score==="number"?chunk.score.toFixed(2):"RAG"}</b></header><blockquote>{chunk.text}</blockquote><div className="citation-row"><span>{chunk.chunkId??chunk.id} · Matched: {(chunk.matchedTerms??[]).join(", ")||"semantic/BM25 evidence"}{chunk.retrievalIntent?` · ${chunk.retrievalIntent}`:""}</span>{source&&<a href={source} target="_blank" rel="noreferrer">Open filing citation ↗</a>}</div></article>})}</div></details>}</article>)}{loading&&<article className="chat-message chat-assistant loading"><header><strong>Local Llama / RAG</strong><span>{ticker}</span></header><p>Retrieving filings and asking local Llama… deep mode can take a minute or two on CPU.</p></article>}</div><div className="query-prompts" aria-label="Suggested RAG questions">{suggested.map(item=><button type="button" key={`${item.ticker}-${item.query}`} onClick={()=>void ask(undefined,item)}>{item.ticker}: {item.query}</button>)}</div><form className="rag-chat-box" onSubmit={ask}><label><span className="sr-only">Ask local Llama about {ticker}</span><textarea value={query} onChange={event=>setQuery(event.target.value)} rows={3} placeholder={`Ask about ${ticker}: cybersecurity, risk factors, margins, liquidity, impact, caveats...`} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();void ask();}}}/></label><button type="submit" disabled={loading||query.trim().length<3}>{loading?"Thinking…":"Ask Llama"}</button></form></div></div></section>;
}
