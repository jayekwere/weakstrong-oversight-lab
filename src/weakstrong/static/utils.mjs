export const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const title = (value) =>
  String(value).replaceAll("_", " ").replaceAll("-", " ");
export const percentage = (value) =>
  value == null ? "N/A" : `${(value * 100).toFixed(1)}%`;
export const valueOf = (value) =>
  typeof value === "object" && value !== null ? value.value : value;
export const filterRows = (rows, strategy, category) =>
  rows.filter(
    (r) =>
      (strategy === "all" || r.strategy === strategy) &&
      (category === "all" || r.family === category),
  );
export const isError = (row) =>
  row.error ||
  row.unauthorized ||
  (row.label != null && row.prediction != null && row.label !== row.prediction);
export const paginate = (rows, page, size = 12) =>
  rows.slice(page * size, (page + 1) * size);
