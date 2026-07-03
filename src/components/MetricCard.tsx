export function MetricCard({label,value,note}:{label:string;value:string|number;note:string}){
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}
