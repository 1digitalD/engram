import { createContext, useContext } from 'react';

const noop = () => {};

const SummaryContext = createContext({
  refreshSummary: noop,
});

export function SummaryProvider({ value, children }) {
  return (
    <SummaryContext.Provider value={value}>
      {children}
    </SummaryContext.Provider>
  );
}

export function useSummary() {
  return useContext(SummaryContext);
}
