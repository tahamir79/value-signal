type RagTeaserProps = {
  ticker: string;
  companyName: string;
};

export function RagTeaser({ ticker, companyName }: RagTeaserProps) {
  return (
    <section className="rag-teaser" aria-labelledby={`rag-teaser-${ticker}`}>
      <div>
        <p className="eyebrow">COMING SOON / FINANCIAL RAG</p>
        <h2 id={`rag-teaser-${ticker}`}>Ask about this stock.</h2>
        <p>
          ValueSignal is preparing a cited research assistant that can summarize SEC filing evidence,
          challenge the official signal, and keep the answer separate from buy/sell/hold advice.
        </p>
      </div>
      <div className="mock-chat-shell" tabIndex={0} aria-label={`Coming soon question box for ${ticker}`}>
        <span>{ticker} evidence assistant</span>
        <p>{companyName}</p>
        <div className="mock-chat-input">Ask about this stock!</div>
        <small className="rag-teaser-bubble">Financial RAG is tested and is soon available.</small>
      </div>
    </section>
  );
}
