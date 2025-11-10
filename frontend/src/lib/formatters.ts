const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export const formatUSD = (value: number): string =>
  currencyFormatter.format(value);

export const formatPercent = (value: number): string =>
  percentFormatter.format(value);
