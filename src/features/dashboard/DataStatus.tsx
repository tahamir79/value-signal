import type { EtlReport } from "@/lib/etl";

function formatInteger(value: number | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : null;
}

export function DataStatus({report}:{report:EtlReport}){
  const live=report.status!=="not_run"&&Boolean(report.runFinishedAt);
  const age=live?Date.now()-new Date(report.runFinishedAt!).getTime():Infinity;
  const stale=age>72*60*60*1000;
  const attempted=report.requestedTickers??report.successfulTickers+report.failedTickers;
  const successRate=attempted>0?report.successfulTickers/attempted:0;
  const userFacingSuccess=live&&report.successfulTickers>0&&successRate>.25;
  const state=report.loadError?"Data load error":userFacingSuccess?"Data pipeline succeeded":live?report.status.replace("_"," "):"Fixture mode";
  const ageNote=stale?" The committed artifact is more than 72 hours old; scheduled business-day batch refreshes are expected to update it.":"";
  const publishedCount=formatInteger(report.fullUniversePublishedTickers);
  const universeSize=formatInteger(report.batchState?.universeSize);
  const nextOffset=report.batchState?.nextOffset;
  const rotationPosition=typeof nextOffset==="number"&&typeof report.batchState?.universeSize==="number"
    ? Math.min(nextOffset,report.batchState.universeSize)
    : undefined;
  const rotationCount=formatInteger(rotationPosition);
  const batchSize=formatInteger(report.batchState?.batchSize);
  const batchCount=formatInteger(report.batchState?.batchCount);
  const batchWindow=batchSize&&batchCount?` The scheduled job is configured as ${batchCount} chunk${report.batchState?.batchCount===1?"":"s"} of ${batchSize} tickers per run.`:"";
  const rotationNote=publishedCount&&universeSize
    ? ` Published artifacts currently cover ${publishedCount} companies. Rotation checkpoint: ${rotationCount??"unknown"} / ${universeSize} active universe rows.${batchWindow}`
    : "";
  const detail=report.loadError?"The ETL report could not be read. The interface is using available fallback observations.":live?`Latest GitHub batch refreshed ${report.successfulTickers} / ${attempted} companies; ${report.failedTickers} failed. Last run ${new Date(report.runFinishedAt!).toLocaleString("en-US",{dateStyle:"medium",timeStyle:"short",timeZone:"UTC"})} UTC.${rotationNote}${ageNote}`:"Live ETL has not run yet. The interface is using Phase 01 placeholder observations.";
  return <aside className={`data-status ${live&&userFacingSuccess&&!report.loadError?"data-live":"data-fixture"}`}><div><span>DATA PIPELINE</span><strong>{state}</strong></div><p>{detail}</p></aside>;
}
