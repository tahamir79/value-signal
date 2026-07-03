import {NextRequest,NextResponse} from "next/server";
import {searchFilings} from "@/lib/search";

export async function GET(request:NextRequest){
  const ticker=(request.nextUrl.searchParams.get("ticker")??"").toUpperCase();
  const query=(request.nextUrl.searchParams.get("q")??"").trim();
  if(!/^[A-Z.\-]{1,10}$/.test(ticker)||query.length<2)return NextResponse.json({error:"A valid ticker and query are required.",results:[]},{status:400});
  const results=await searchFilings(ticker,query);
  return NextResponse.json({ticker,query,results});
}
