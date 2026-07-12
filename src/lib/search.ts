import "server-only";
import {readFile} from "node:fs/promises";
import path from "node:path";

export type FilingEvidence={
  id:string;chunkId?:string;ticker:string;companyName?:string;cik?:string|null;
  accession:string;filingDate:string;reportDate?:string;form:string;formType?:string;
  primaryDocument?:string|null;part?:string|null;itemNumber?:string|null;
  sectionKey?:string|null;sectionTitle?:string|null;item:string;
  chunkSequence?:number;boundaryType?:string;paragraphRange?:[number,number]|null;
  sentenceRange?:[number,number]|null;sectionWordStart?:number|null;sectionWordEnd?:number|null;
  documentWordStart?:number|null;documentWordEnd?:number|null;documentCharStart?:number|null;
  documentCharEnd?:number|null;previousChunkId?:string|null;nextChunkId?:string|null;
  sourcePath?:string|null;sourceUrl?:string|null;url:string;text:string;score:number;matchedTerms:string[]
};
type IndexedEvidence=Omit<FilingEvidence,"score"|"matchedTerms">;
type SearchIndex={schemaVersion?:string;documentCount:number;averageDocumentLength:number;documentLengths:number[];documents:IndexedEvidence[];postings:Record<string,Array<[number,number]>>};
type SearchManifest={indexMode?:"per_ticker";tickers?:Record<string,{path:string;documentCount:number;latestFilingDate?:string|null}>};
const stopwords=new Set(["a","an","and","are","as","at","be","by","for","from","has","in","is","it","of","on","or","that","the","this","to","was","were","will","with"]);
const tokenize=(text:string)=>(text.toLowerCase().match(/[a-z0-9]+(?:'[a-z]+)?/g)??[]).filter(token=>!stopwords.has(token)&&token.length>1);
const section=(row:FilingEvidence)=>row.sectionKey??row.item??"";
const similarity=(left:string,right:string)=>{const a=new Set(tokenize(left)),b=new Set(tokenize(right));if(!a.size&&!b.size)return 1;let overlap=0;for(const token of a)if(b.has(token))overlap++;return overlap/(a.size+b.size-overlap)};

/** Deterministic post-ranking only: BM25 scores and ordering remain untouched. */
export function diversifyEvidence(ranked:FilingEvidence[],limit:number):FilingEvidence[]{
  if(!ranked.length||limit<1)return [];
  const selected=[ranked[0]],used=new Set([ranked[0].id]);
  const acceptable=(row:FilingEvidence)=>!selected.some(chosen=>similarity(row.text,chosen.text)>.70);
  for(const row of ranked.slice(1)){
    if(selected.length>=limit)break;
    if(row.score<ranked[0].score*.25||used.has(row.id)||!acceptable(row))continue;
    if(!selected.some(chosen=>section(chosen)===section(row))){selected.push(row);used.add(row.id)}
  }
  for(const row of ranked.slice(1)){
    if(selected.length>=limit)break;
    if(!used.has(row.id)&&acceptable(row)){selected.push(row);used.add(row.id)}
  }
  return selected;
}

const emptyIndex=():SearchIndex=>({documentCount:0,averageDocumentLength:0,documentLengths:[],documents:[],postings:{}});

async function loadIndex(ticker:string):Promise<SearchIndex>{
  const root=path.join(process.cwd(),"public","data","search_index.json");
  const payload=JSON.parse(await readFile(root,"utf8")) as SearchIndex&SearchManifest;
  if(payload.indexMode==="per_ticker"){
    const entry=payload.tickers?.[ticker];
    if(!entry?.path)return emptyIndex();
    return JSON.parse(await readFile(path.join(process.cwd(),entry.path),"utf8")) as SearchIndex;
  }
  return payload as SearchIndex;
}

export async function searchFilings(ticker:string,query:string,limit=5):Promise<FilingEvidence[]>{
  const normalizedTicker=ticker.toUpperCase(),terms=tokenize(query.slice(0,200));if(!terms.length)return [];
  try{const index=await loadIndex(normalizedTicker),scores=new Map<number,number>(),average=index.averageDocumentLength||1;
    for(const term of terms){const posting=index.postings[term]??[];if(!posting.length)continue;const inverse=Math.log(1+(index.documentCount-posting.length+.5)/(posting.length+.5));for(const [docId,frequency] of posting){if(index.documents[docId]?.ticker!==normalizedTicker)continue;const length=index.documentLengths[docId];const score=inverse*(frequency*2.5)/(frequency+1.5*(.25+.75*length/average));scores.set(docId,(scores.get(docId)??0)+score)}}
    const ranked=[...scores.entries()].sort((a,b)=>b[1]-a[1]||a[0]-b[0]).map(([docId,score])=>({...index.documents[docId],score:Number(score.toFixed(6)),matchedTerms:terms.filter(term=>(index.postings[term]??[]).some(([id])=>id===docId))}));
    return diversifyEvidence(ranked,Math.max(1,Math.min(limit,10)));
  }catch{return []}
}
