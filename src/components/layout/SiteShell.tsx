import Link from "next/link";
import Image from "next/image";
import { AuthStatus } from "@/components/AuthStatus";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";

export function SiteShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="site-header">
        <Link className="brand" href="/" aria-label="ValueSignal home">
          <Image className="brand-mark" src="/valuesignal-logo.png" alt="" width={42} height={42} priority />
          <span>VALUE SIGNAL<small>Evidence before opinion</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/rag">RAG</Link>
          <Link href="/methodology">Methodology</Link>
        </nav>
        <AuthStatus />
        <span className="mode-mark">RESEARCH / LITE</span>
      </header>
      <main>{children}</main>
      <footer>
        <div><strong>ValueSignal</strong><span>Transparent public-company research support.</span></div>
        <Disclaimer compact />
      </footer>
    </>
  );
}
