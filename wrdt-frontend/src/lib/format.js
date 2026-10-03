/** Shared formatting helpers. */

export const inr = (n) =>
  "\u20b9" + new Intl.NumberFormat("en-IN").format(Math.round(Number(n) || 0));

export const num = (n) => new Intl.NumberFormat("en-IN").format(Number(n) || 0);

export const fmtDate = (d) => {
  if (!d) return "\u2014";
  try {
    return new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return d;
  }
};

export const fmtDateTime = (d) => {
  if (!d) return "\u2014";
  try {
    return new Date(d).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return d;
  }
};

export const initials = (n = "") =>
  n.split(" ").filter(Boolean).slice(0, 2).map((x) => x[0].toUpperCase()).join("");

export const greeting = (t) => {
  const h = new Date().getHours();
  return h < 12 ? t.goodMorn : h < 17 ? t.goodAftn : t.goodEvng;
};

/** Money coming back from the API is a decimal string; never use
 *  parseFloat for display maths, only for comparison/formatting. */
export const dec = (v) => (v === null || v === undefined ? 0 : Number(v));
