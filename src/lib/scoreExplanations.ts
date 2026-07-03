export const scoreExplanations:Record<string,{tone:"support"|"risk"|"context";label:string}>={
  VALUE_STRONG:{tone:"support",label:"Strong relative valuation evidence"},
  VALUE_WEAK:{tone:"risk",label:"Weak relative valuation evidence"},
  QUALITY_STRONG:{tone:"support",label:"Strong profitability and growth evidence"},
  QUALITY_WEAK:{tone:"risk",label:"Weak or deteriorating quality evidence"},
  MOMENTUM_RISK_HIGH:{tone:"risk",label:"Elevated momentum risk"},
  MARKET_RISK_HIGH:{tone:"risk",label:"Elevated volatility or drawdown risk"},
  BALANCE_SHEET_RISK_HIGH:{tone:"risk",label:"Elevated balance-sheet risk"},
  EVIDENCE_SPARSE:{tone:"risk",label:"Insufficient feature evidence"},
  EVIDENCE_PARTIAL:{tone:"context",label:"Partial feature coverage"},
  EVIDENCE_COMPLETE:{tone:"context",label:"Nearly complete feature coverage"},
};
