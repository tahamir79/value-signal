import {spawn} from "node:child_process";
import {NextRequest,NextResponse} from "next/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";

type RagPayload={query:string;ticker?:string;form?:string;mode?:string;topK?:number;depth?:string;sessionSummary?:string;synthesize?:boolean};

function isLocalRequest(request:NextRequest){
  const host=request.headers.get("host")??"";
  return process.env.NODE_ENV==="development"||host.startsWith("localhost")||host.startsWith("127.0.0.1");
}

function runPythonRag(payload:RagPayload){
  return new Promise<Record<string,unknown>>((resolve,reject)=>{
    const args=["scripts/run_rag.py",payload.query,"--mode",payload.mode??"hybrid","--top-k",String(payload.topK??3)];
    args.push("--depth",payload.depth==="quick"?"quick":"deep");
    if(payload.ticker)args.push("--ticker",payload.ticker.toUpperCase());
    if(payload.form)args.push("--form",payload.form);
    if(payload.sessionSummary)args.push("--session-summary",payload.sessionSummary.slice(0,1800));
    if(payload.synthesize===false)args.push("--no-synthesize");
    const child=spawn(process.env.PYTHON??"python",args,{cwd:process.cwd(),env:{...process.env,PYTHONIOENCODING:"utf-8"}});
    let stdout="",stderr="";
    const timeout=setTimeout(()=>child.kill(),180_000);
    child.stdout.on("data",chunk=>{stdout+=chunk.toString();});
    child.stderr.on("data",chunk=>{stderr+=chunk.toString();});
    child.on("error",error=>{clearTimeout(timeout);reject(error);});
    child.on("close",code=>{
      clearTimeout(timeout);
      if(code!==0)return reject(new Error(stderr||`RAG process exited with code ${code}.`));
      try{resolve(JSON.parse(stdout));}
      catch(error){reject(new Error(`RAG returned invalid JSON. ${error instanceof Error?error.message:String(error)}`));}
    });
  });
}

export async function POST(request:NextRequest){
  if(!isLocalRequest(request)){
    return NextResponse.json({error:"Local RAG is disabled outside local development. Run `npm run dev` with Ollama running to use it."},{status:403});
  }
  const body=await request.json().catch(()=>null) as RagPayload|null;
  const query=(body?.query??"").trim();
  const ticker=(body?.ticker??"").trim().toUpperCase();
  const form=(body?.form??"").trim();
  const mode=body?.mode??"hybrid";
  const topK=Math.min(Math.max(Number(body?.topK??3),1),8);
  const depth=body?.depth==="quick"?"quick":"deep";
  if(query.length<3)return NextResponse.json({error:"Enter a research question with at least 3 characters."},{status:400});
  if(ticker&&!/^[A-Z.\-]{1,10}$/.test(ticker))return NextResponse.json({error:"Ticker must be 1-10 letters, dots, or dashes."},{status:400});
  if(!["bm25","embedding","hybrid"].includes(mode))return NextResponse.json({error:"Mode must be bm25, embedding, or hybrid."},{status:400});
  try{
    const result=await runPythonRag({query,ticker:ticker||undefined,form:form||undefined,mode,topK,depth,sessionSummary:body?.sessionSummary,synthesize:body?.synthesize!==false});
    return NextResponse.json(result);
  }catch(error){
    return NextResponse.json({error:error instanceof Error?error.message:String(error)},{status:500});
  }
}
