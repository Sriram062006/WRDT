import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync, useDebounced } from "../lib/useAsync.js";
import { num } from "../lib/format.js";
import { TableCard } from "../components/Card.jsx";
import {
  Badge, Btn, ConfirmModal, EmptyState, ErrorState, Field, IconBtn, InlineError,
  Loading, Modal, PageHead, Pagination, SearchInput, fieldStyle,
} from "../components/ui.jsx";

const PAGE_SIZE = 20;

export default function Regions({ t, go }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [modal, setModal] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);

  const list = useAsync(
    () => api.listRegions({ page, page_size: PAGE_SIZE, q: dq || undefined }),
    [page, dq]
  );

  const save = async (e) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      if (modal.mode === "add") await api.createRegion(modal.name);
      else await api.updateRegion(modal.region.id, { name: modal.name });
      setModal(null);
      list.reload();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteRegion(deleting.id);
      setDeleting(null);
      list.reload();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHead
        title={t.regions}
        sub="Regions contain groups, which contain members."
        actions={
          <Btn icon="Plus" onClick={() => { setModal({ mode: "add", name: "" }); setFormError(null); }}>
            {t.addRegion}
          </Btn>
        }
      />

      <TableCard
        toolbar={<SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder={t.search} />}
        footer={
          list.data && (
            <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />
          )
        }
      >
        {list.loading ? (
          <Loading label={t.loading} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data.items.length === 0 ? (
          <EmptyState
            icon="MapPin"
            title={dq ? "No regions match that search." : "No regions yet."}
            message={dq ? undefined : "Add your first region, or import your existing register from Excel."}
          />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.regionName}</th>
                <th className="num">{t.groups}</th>
                <th className="num">{t.members}</th>
                <th>{t.status}</th>
                <th style={{ width: 96 }}>{t.action}</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <button
                      onClick={() => go("groups", { regionId: r.id, regionName: r.name })}
                      style={{ background: "none", border: "none", padding: 0, fontSize: 13, fontWeight: 600, color: "var(--brand)", textAlign: "left" }}
                    >
                      {r.name}
                    </button>
                  </td>
                  <td className="num muted">{num(r.groups_count)}</td>
                  <td className="num muted">{num(r.members_count)}</td>
                  <td><Badge s={r.status} /></td>
                  <td>
                    <div className="row">
                      <IconBtn n="Edit" title={t.edit} onClick={() => { setModal({ mode: "edit", region: r, name: r.name }); setFormError(null); }} />
                      <IconBtn n="Trash2" title={t.del} color="var(--err)" onClick={() => { setDeleting(r); setFormError(null); }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>

      {modal && (
        <Modal title={modal.mode === "add" ? t.addRegion : `${t.edit} ${t.regions}`} onClose={() => setModal(null)}>
          <form onSubmit={save}>
            <InlineError error={formError} />
            <Field label={t.regionName}>
              <input
                autoFocus
                required
                value={modal.name}
                onChange={(e) => setModal({ ...modal, name: e.target.value })}
                placeholder="e.g. Jagadevi"
                style={fieldStyle}
              />
            </Field>
            <div className="row" style={{ gap: 10 }}>
              <div className="spacer" />
              <Btn variant="secondary" onClick={() => setModal(null)} disabled={busy}>{t.cancel}</Btn>
              <Btn type="submit" disabled={busy}>{busy ? "Saving..." : t.save}</Btn>
            </div>
          </form>
        </Modal>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete region?"
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={remove}
          message={
            <>
              Delete <strong>{deleting.name}</strong>?
              {deleting.groups_count > 0 && (
                <>
                  {" "}It contains <strong>{deleting.groups_count}</strong> group(s) and{" "}
                  <strong>{deleting.members_count}</strong> member(s), which will be removed with it.
                  Completed meeting history is retained for audit.
                </>
              )}
            </>
          }
        />
      )}
    </div>
  );
}
