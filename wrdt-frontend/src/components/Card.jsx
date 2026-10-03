export function Card({ title, actions, children, pad = true }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="row wrap" style={{ padding: "12px 16px", borderBottom: "1px solid var(--bdr)", gap: 10 }}>
          {title && <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>}
          <div className="spacer" />
          {actions}
        </div>
      )}
      <div style={pad ? { padding: 16 } : undefined}>{children}</div>
    </section>
  );
}

/** A card whose body is a table -- no padding, so the table's own
 *  borders reach the card edge. */
export function TableCard({ toolbar, children, footer }) {
  return (
    <section className="card" style={{ overflow: "hidden" }}>
      {toolbar && (
        <div className="row wrap" style={{ padding: "12px 14px", borderBottom: "1px solid var(--bdr)", gap: 10 }}>
          {toolbar}
        </div>
      )}
      <div className="table-wrap">{children}</div>
      {footer}
    </section>
  );
}
