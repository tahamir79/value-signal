import Link from "next/link";
export default function StockNotFound() { return <div className="page empty-state"><p className="eyebrow">UNKNOWN TICKER</p><h1>No research record found.</h1><p>This starter universe contains ten placeholder companies.</p><Link className="button" href="/dashboard">Return to dashboard</Link></div>; }
