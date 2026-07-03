import "server-only";
import {readFile} from "node:fs/promises";
import path from "node:path";

export type FilingEvidence={id:string;ticker:string;accession:string;filingDate:string;reportDate:string;form:string;item:string;url:string;text:string;score:number;matchedTerms:string[]};
type SearchIndex={documentCount:number;averageDocumentLength:number;documentLengths:number[];documents:Array<Omit<FilingEvidence,"score"|"matchedTerms">>;postings:Record<string,Array<[number,number]>>};
const stopwords=new Set(["a","an","and","are","as","at","be","by","for","from","has","in","is","it","of","on","or","that","the","this","to","was","were","will","with"]);
const tokenize=(text:string)=>(text.toLowerCase().match(/[a-z0-9]+(?:'[a-z]+)?/g)??[]).filter(token=>!stopwords.has(token)&&token.length>1);

async function loadIndex():Promise<SearchIndex>{return JSON.parse(await readFile(path.join(process.cwd(),"public","data","search_index.json"),"utf8")) as SearchIndex}

export async function searchFilings(ticker:string,query:string,limit=5):Promise<FilingEvidence[]>{
  const normalizedTicker=ticker.toUpperCase();const terms=tokenize(query.slice(0,200));if(!terms.length)return [];
  try{
    const index=await loadIndex();const scores=new Map<number,number>();const average=index.averageDocumentLength||1;
    for(const term of terms){const posting=index.postings[term]??[];if(!posting.length)continue;const inverse=Math.log(1+(index.documentCount-posting.length+.5)/(posting.length+.5));for(const [docId,frequency] of posting){if(index.documents[docId]?.ticker!==normalizedTicker)continue;const length=index.documentLengths[docId];const score=inverse*(frequency*2.5)/(frequency+1.5*(.25+.75*length/average));scores.set(docId,(scores.get(docId)??0)+score)}}
    return [...scores.entries()].sort((a,b)=>b[1]-a[1]||a[0]-b[0]).slice(0,Math.max(1,Math.min(limit,10))).map(([docId,score])=>({...index.documents[docId],score:Number(score.toFixed(6)),matchedTerms:terms.filter(term=>(index.postings[term]??[]).some(([id])=>id===docId))}));
  }catch{return []}
}
