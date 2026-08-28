import type { EtlReport } from "@/lib/etl";

function formatInteger(value: number | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : null;
}

export function DataStatus({report}:{report:EtlReport}){
  const showDiagnostics=process.env.NODE_ENV!=="production"||process.env.NEXT_PUBLIC_VS_DIAGNOSTIC_STATUS==="true";
  const live=report.status!=="not_run"&&Boolean(report.runFinishedAt);
  const age=live?Date.now()-new Date(report.runFinishedAt!).getTime():Infinity;
  const stale=age>72*60*60*1000;
  const attempted=report.requestedTickers??report.successfulTickers+report.failedTickers;
  const successRate=attempted>0?report.successfulTickers/attempted:0;
  const userFacingSuccess=live&&report.successfulTickers>0&&successRate>.25;
  const state=report.loadError?"Data unavailable":userFacingSuccess?showDiagnostics?"Data pipeline succeeded":"Research data updated":live?"Data refresh limited":"Fixture mode";
  const ageNote=stale?" The committed artifact is more than 72 hours old; scheduled business-day batch refreshes are expected to update it.":"";
  const publishedCount=formatInteger(report.fullUniversePublishedTickers);
  const attemptedCount=formatInteger(attempted);
  const successfulCount=formatInteger(report.successfulTickers);
  const universeSize=formatInteger(report.batchState?.universeSize);
  const nextOffset=report.batchState?.nextOffset;
  const rotationPosition=typeof nextOffset==="number"&&typeof report.batchState?.universeSize==="number"
    ? Math.min(nextOffset,report.batchState.universeSize)
    : undefined;
  const rotationCount=formatInteger(rotationPosition);
  const batchSize=formatInteger(report.batchState?.batchSize);
  const batchCount=formatInteger(report.batchState?.batchCount);
  const dailySweepSlots=formatInteger(report.batchState?.dailySweepSlots);
  const plannedDailyRefreshTickers=formatInteger(report.batchState?.plannedDailyRefreshTickers);
  const batchWindow=batchSize&&batchCount?` The scheduled job is configured as ${batchCount} chunk${report.batchState?.batchCount===1?"":"s"} of ${batchSize} tickers per run${dailySweepSlots&&plannedDailyRefreshTickers?`, across ${dailySweepSlots} weekday sweep slots for up to ${plannedDailyRefreshTickers} tickers per business-day sweep.`:"."}`:"";
  const rotationNote=publishedCount&&universeSize
    ? ` Published artifacts currently cover ${publishedCount} companies. Rotation checkpoint: ${rotationCount??"unknown"} / ${universeSize} active universe rows.${batchWindow}`
    : "";
  const updatedAt=live?new Date(report.runFinishedAt!).toLocaleString("en-US",{dateStyle:"medium",timeStyle:"short",timeZone:"UTC"}):null;
  const publicDetail=report.loadError
    ?"Research data is temporarily unavailable. Showing the latest bundled observations where possible."
    :live
      ? `Updated ${updatedAt} UTC. Latest refresh covered ${successfulCount??report.successfulTickers} / ${attemptedCount??attempted} companies${publishedCount?`; ${publishedCount} companies are available in the current research universe.`:"."}`
      :"Live research data has not run yet. Showing starter observations.";
  const diagnosticDetail=report.loadError?"The ETL report could not be read. The interface is using available fallback observations.":live?`Latest GitHub batch refreshed ${report.successfulTickers} / ${attempted} companies; ${report.failedTickers} failed. Last run ${updatedAt} UTC.${rotationNote}${ageNote}`:"Live ETL has not run yet. The interface is using Phase 01 placeholder observations.";
  const detail=showDiagnostics?diagnosticDetail:publicDetail;
  return <aside className={`data-status ${showDiagnostics?"data-diagnostic":"data-public"} ${live&&userFacingSuccess&&!report.loadError?"data-live":"data-fixture"}`}><div><span>{showDiagnostics?"DATA PIPELINE":"DATA FRESHNESS"}</span><strong>{state}</strong></div><p>{detail}</p></aside>;
}
