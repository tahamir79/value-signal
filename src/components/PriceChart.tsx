import type { PriceBar } from "@/lib/etl";

function shortDate(value:string){return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US",{month:"short",year:"2-digit",timeZone:"UTC"})}

export function PriceChart({prices}:{prices:PriceBar[]}){
  const points=prices.filter(bar=>Number.isFinite(bar.adjusted_close??bar.close)).slice(-130);
  if(points.length<2)return <div className="chart-empty" role="status">Price history is unavailable for this record.</div>;
  const values=points.map(bar=>bar.adjusted_close??bar.close);
  const min=Math.min(...values),max=Math.max(...values),range=max-min||1;
  const width=720,height=260,pad=18;
  const coords=values.map((value,index)=>{
    const x=pad+(index/(values.length-1))*(width-pad*2);
    const y=pad+(1-(value-min)/range)*(height-pad*2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const first=points[0],last=points.at(-1)!;
  return <figure className="price-chart">
    <div className="chart-heading"><div><p className="eyebrow">PRICE HISTORY</p><h2>Recent adjusted close</h2></div><p>{shortDate(first.date)}–{shortDate(last.date)} · {points.length} trading sessions</p></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="price-chart-title price-chart-desc">
      <title id="price-chart-title">Adjusted closing price history</title>
      <desc id="price-chart-desc">From ${values[0].toFixed(2)} on {first.date} to ${values.at(-1)!.toFixed(2)} on {last.date}. Period low ${min.toFixed(2)} and high ${max.toFixed(2)}.</desc>
      <line x1={pad} y1={pad} x2={width-pad} y2={pad}/><line x1={pad} y1={height-pad} x2={width-pad} y2={height-pad}/>
      <polyline points={coords}/>
    </svg>
    <figcaption><span>Low <strong>${min.toFixed(2)}</strong></span><span>High <strong>${max.toFixed(2)}</strong></span><span>Latest <strong>${values.at(-1)!.toFixed(2)}</strong></span></figcaption>
  </figure>;
}
