"use client";

import {useState} from "react";
import {briefToMarkdown,type AnalystBriefData} from "@/lib/briefGenerator";

export function AnalystBrief({brief}:{brief:AnalystBriefData}){
  const [copied,setCopied]=useState(false);
  async function copy(){await navigator.clipboard.writeText(briefToMarkdown(brief));setCopied(true);window.setTimeout(()=>setCopied(false),1800)}
  return <section className="analyst-brief" aria-labelledby="analyst-brief-title"><header><div><p className="eyebrow">DETERMINISTIC ANALYST BRIEF</p><h2 id="analyst-brief-title">{brief.title}</h2><p>{brief.summary}</p></div><div className="brief-actions"><button type="button" onClick={copy}>{copied?"Copied":"Copy Markdown"}</button><button type="button" onClick={()=>window.print()}>Print brief</button></div></header><div className="brief-grid"><article><h3>Validated facts</h3>{brief.claims.length?<ul>{brief.claims.map(claim=><li key={claim.id}><span>{claim.text}</span><code>{claim.sourceRef}</code></li>)}</ul>:<p>No validated claims are available.</p>}</article><article className="brief-missing"><h3>Missing sections</h3><ul>{brief.missingSections.map(item=><li key={item}>{item}</li>)}</ul></article></div><article className="brief-citations"><h3>Retrieved filing evidence</h3><p>These passages are cited source evidence, not ValueSignal conclusions.</p>{brief.filingEvidence.length?<div>{brief.filingEvidence.map(item=><blockquote key={item.id}><p>{item.text}</p><cite>{item.form} · {item.item} · filed {item.filingDate} · <a href={item.url} target="_blank" rel="noreferrer">SEC accession {item.accession}</a></cite></blockquote>)}</div>:<p className="brief-empty">No cited filing passages are available.</p>}</article><article className="brief-questions"><h3>Research next</h3><ol>{brief.researchQuestions.map(question=><li key={question}>{question}</li>)}</ol></article><p className="brief-disclaimer">{brief.disclaimer}</p></section>;
}
