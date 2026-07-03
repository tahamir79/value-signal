"use client";

import { useMemo,useState,type KeyboardEvent,type PointerEvent } from "react";
import type { PriceBar } from "@/lib/etl";

function shortDate(value:string){return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US",{month:"short",year:"2-digit",timeZone:"UTC"})}
function fullDate(value:string){return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"})}

export function PriceChart({prices}:{prices:PriceBar[]}){
  const points=useMemo(()=>prices.filter(bar=>Number.isFinite(bar.adjusted_close??bar.close)).slice(-130),[prices]);
  const [active,setActive]=useState<number|null>(null);
  if(points.length<2)return <div className="chart-empty" role="status">Price history is unavailable for this record.</div>;
  const values=points.map(bar=>bar.adjusted_close??bar.close),min=Math.min(...values),max=Math.max(...values),range=max-min||1;
  const width=760,height=330,left=64,right=20,top=20,bottom=42,plotWidth=width-left-right,plotHeight=height-top-bottom;
  const x=(index:number)=>left+(index/(values.length-1))*plotWidth;
  const y=(value:number)=>top+(1-(value-min)/range)*plotHeight;
  const coords=values.map((value,index)=>`${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const yTicks=Array.from({length:5},(_,index)=>max-(range*index)/4);
  const xIndexes=Array.from(new Set([0,Math.round((points.length-1)/4),Math.round((points.length-1)/2),Math.round((points.length-1)*.75),points.length-1]));
  const selected=active===null?null:{bar:points[active],value:values[active],x:x(active),y:y(values[active])};
  function move(event:PointerEvent<SVGSVGElement>){const box=event.currentTarget.getBoundingClientRect();const chartX=((event.clientX-box.left)/box.width)*width;setActive(Math.max(0,Math.min(points.length-1,Math.round(((chartX-left)/plotWidth)*(points.length-1)))))}
  function key(event:KeyboardEvent<SVGSVGElement>){if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight"&&event.key!=="Home"&&event.key!=="End")return;event.preventDefault();setActive(current=>event.key==="Home"?0:event.key==="End"?points.length-1:Math.max(0,Math.min(points.length-1,(current??points.length-1)+(event.key==="ArrowLeft"?-1:1))))}
  return <figure className="price-chart">
    <div className="chart-heading"><div><p className="eyebrow">PRICE HISTORY</p><h2>Recent adjusted close</h2></div><p>{shortDate(points[0].date)}–{shortDate(points.at(-1)!.date)} · {points.length} trading sessions</p></div>
    <div className="chart-stage"><svg viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} aria-labelledby="price-chart-title price-chart-desc" onPointerMove={move} onPointerLeave={()=>setActive(null)} onFocus={()=>setActive(value=>value??points.length-1)} onKeyDown={key}>
      <title id="price-chart-title">Interactive adjusted closing price history</title><desc id="price-chart-desc">Move across the chart or use left and right arrow keys to inspect date and price coordinates. Period low ${min.toFixed(2)} and high ${max.toFixed(2)}.</desc>
      {yTicks.map(value=><g className="chart-grid" key={value}><line x1={left} y1={y(value)} x2={width-right} y2={y(value)}/><text x={left-10} y={y(value)+4} textAnchor="end">${value.toFixed(2)}</text></g>)}
      {xIndexes.map(index=><g className="chart-grid" key={index}><line x1={x(index)} y1={top} x2={x(index)} y2={height-bottom}/><text x={x(index)} y={height-14} textAnchor={index===0?"start":index===points.length-1?"end":"middle"}>{shortDate(points[index].date)}</text></g>)}
      <polyline className="chart-line" points={coords}/><rect className="chart-hit-area" x={left} y={top} width={plotWidth} height={plotHeight}/>
      {selected&&<g className="chart-cursor" aria-hidden="true"><line x1={selected.x} y1={top} x2={selected.x} y2={height-bottom}/><line x1={left} y1={selected.y} x2={width-right} y2={selected.y}/><circle cx={selected.x} cy={selected.y} r="6"/></g>}
    </svg>{selected&&<div className="chart-tooltip" style={{left:`${(selected.x/width)*100}%`,top:`${(selected.y/height)*100}%`}}><span>{fullDate(selected.bar.date)}</span><strong>${selected.value.toFixed(2)}</strong><small>Volume {selected.bar.volume.toLocaleString()}</small></div>}</div>
    <div className="chart-coordinate" aria-live="polite">{selected?`${fullDate(selected.bar.date)}: $${selected.value.toFixed(2)}`:"Hover, touch, or focus the chart to inspect a coordinate."}</div>
    <figcaption><span>Low <strong>${min.toFixed(2)}</strong></span><span>High <strong>${max.toFixed(2)}</strong></span><span>Latest <strong>${values.at(-1)!.toFixed(2)}</strong></span></figcaption>
  </figure>;
}
