import type { EtlReport } from "@/lib/etl";
export function DataStatus({report}:{report:EtlReport}){
  const live=report.status!=="not_run"&&Boolean(report.runFinishedAt);
  const age=live?Date.now()-new Date(report.runFinishedAt!).getTime():Infinity;
  const stale=age>72*60*60*1000;
  const attempted=report.requestedTickers??report.successfulTickers+report.failedTickers;
  const successRate=attempted>0?report.successfulTickers/attempted:0;
  const userFacingSuccess=live&&report.successfulTickers>0&&successRate>.25;
  const state=report.loadError?"Data load error":stale&&live?"Stale data":userFacingSuccess?"Data pipeline succeeded":live?report.status.replace("_"," "):"Fixture mode";
  const detail=report.loadError?"The ETL report could not be read. The interface is using available fallback observations.":live?`${report.successfulTickers} companies refreshed; ${report.failedTickers} failed. Last run ${new Date(report.runFinishedAt!).toLocaleString("en-US",{dateStyle:"medium",timeStyle:"short",timeZone:"UTC"})} UTC.${stale?" This dataset is more than 72 hours old.":""}`:"Live ETL has not run yet. The interface is using Phase 01 placeholder observations.";
  return <aside className={`data-status ${live&&!stale&&!report.loadError?"data-live":"data-fixture"}`}><div><span>DATA PIPELINE</span><strong>{state}</strong></div><p>{detail}</p></aside>;
}
