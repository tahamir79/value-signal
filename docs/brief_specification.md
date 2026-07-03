# ValueSignal analyst brief specification v1.0.0

Analyst briefs are deterministic views over validated ValueSignal inputs. They do not use a language model and do not create facts.

## Evidence hierarchy

1. Current signal label and confidence from `signals.json`.
2. Valid component scores in the inclusive range 0–100.
3. Matching point-in-time backtest cohort with explicit sample size.
4. Retrieved SEC passages with filing metadata and direct citations.
5. System-generated research questions, clearly presented as questions rather than claims.

Every generated factual claim stores a source type and source reference. Filing passages remain quoted source evidence and are never converted into conclusions.

## Missingness and language

- Invalid or null scores are omitted and listed in the missing-sections panel.
- Missing backtest cohorts and filing passages are disclosed explicitly.
- Backtest context includes horizon, sample size, mean excess return, and win rate, followed by a non-forecast caveat.
- Templates avoid investment instructions, promotional adjectives, certainty, and personalized language.
- Each of the six signal labels has a fixed title and summary template.

## Review and export

The rendered brief includes claim provenance, citations, missing sections, and unanswered research questions. Users can copy the complete brief as Markdown or print a brief-only view for human review.
