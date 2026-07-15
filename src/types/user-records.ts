export type WatchlistItem = {
  id: string;
  userId: string;
  ticker: string;
  companyName: string;
  createdAt: string;
  alertEnabled: boolean;
  companyEventAlerts: boolean;
  industryEventAlerts: boolean;
  filingAlerts: boolean;
  signalChangeAlerts: boolean;
  forecastChangeAlerts: boolean;
};

export type WatchlistAlertPatch = Partial<Pick<
  WatchlistItem,
  "alertEnabled" | "companyEventAlerts" | "industryEventAlerts" | "filingAlerts" | "signalChangeAlerts" | "forecastChangeAlerts"
>>;

export type PortfolioPosition = {
  id: string;
  userId: string;
  ticker: string;
  companyName: string;
  positionStatus: "owned" | "planned";
  quantityType: "shares" | "dollar_amount";
  shares: number | null;
  dollarAmount: number | null;
  averageCostPerShare: number | null;
  userReturnEstimate30Day: number | null;
  userReturnEstimate90Day: number | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PortfolioPositionInput = {
  ticker: string;
  positionStatus: "owned" | "planned";
  quantityType: "shares" | "dollar_amount";
  shares?: number | null;
  dollarAmount?: number | null;
  averageCostPerShare?: number | null;
  userReturnEstimate30Day?: number | null;
  userReturnEstimate90Day?: number | null;
  notes?: string | null;
};
