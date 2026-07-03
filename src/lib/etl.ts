import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
export type EtlData={schemaVersion:string;generatedAt:string|null;mode:"live"|"fixture";records:Array<{security:{ticker:string};derived:{latestPrice:number|null;dailyChangePercent:number|null;marketCapBillions:number|null}}>};
export type EtlReport={status:"not_run"|"success"|"partial_success";runFinishedAt:string|null;successfulTickers:number;failedTickers:number};
export type SignalData={schemaVersion:string;generatedAt:string|null;records:Array<{ticker:string;asOf:string;signal:string;confidence:"High"|"Medium"|"Low"|"Insufficient";scores:{value:number|null;quality:number|null;momentum:number|null;marketRisk:number|null;balanceSheetRisk:number|null};reasonCodes:string[];explanations:string[]}>};
async function read<T>(name:string):Promise<T>{return JSON.parse(await readFile(path.join(process.cwd(),"public","data",name),"utf8")) as T}
export async function getEtlData(){return read<EtlData>("dashboard.json")}
export async function getEtlReport(){return read<EtlReport>("etl_report.json")}
export async function getSignalData(){return read<SignalData>("signals.json")}
