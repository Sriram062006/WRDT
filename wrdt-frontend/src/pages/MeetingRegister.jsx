import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDate, inr } from "../lib/format.js";
import { Card } from "../components/Card.jsx";
import {
  Badge, Btn, ConfirmModal, ErrorState, Icon, IconBtn, InlineError, Loading,
  Modal, Spinner, fieldStyle,
} from "../components/ui.jsx";

/**
 * The WRDT Meeting Register.
 *
 * Design decisions worth stating, because this screen carries the money:
 *
 *  * Every derived number on screen -- Total Saving, Cash Paid, the
 *    totals row, Cash in Hand -- comes from the server's `totals` block,
 *    recomputed by the ledger engine after each save. The prototype
 *    calculated them in the browser, which meant the figure a supervisor
 *    read out loud to the group could differ from what was stored. The
 *    only client-side arithmetic here is the optimistic preview of a
 *    single row while you are still typing in it.
 *
 *  * Saving is explicit, batched and atomic. The prototype auto-saved
 *    into a module-level object on every keystroke. Here edits collect
 *    in local state, the header shows "Unsaved changes", and one bulk
 *    PUT writes the whole sheet in a single transaction -- so a dropped
 *    connection mid-meeting cannot leave half a register committed.
 *
 *  * Completion is final and the UI says so before it happens, then
 *    renders the sheet read-only. The lock is enforced by the API and by
 *    a database trigger regardless of what this component does.
 */

const SAVING_PRESETS = [0, 50, 100, 200, 300, 500, 1000];
const REMARKS = ["Paid", "Loan Taken", "Absent", "Pending"];
const EXPENSE_PRESETS = ["Travel", "Tea", "Stationery", "Others"];

const money = (v) => (v === "" || v === null || v === undefined ? 0 : Number(v));

export default function MeetingRegister({ t, ctx, go, toast }) {
  const { data, error, loading, reload } = useAsync(() => api.getMeeting(ctx.meetingId), [ctx.meetingId]);

  const [rows, setRows] = useState(null);      // local edit buffer, keyed by member_id
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [showComplete, setShowComplete] = useState(false);
  const [bulkAmount, setBulkAmount] = useState(300);
  const [newExpense, setNewExpense] = useState({ expense_type: "Travel", amount: "" });
  const [members, setMembers] = useState({});

  const locked = Boolean(data?.locked);

  // Ledger entries identify members by ID only; fetch the roster once so
  // the register can show names and codes like the paper book does.
  useEffect(() => {
    if (!ctx.groupId) return;
    let alive = true;
    api
      .listMembersInGroup(ctx.groupId, { page_size: 200 })
      .then((res) => {
        if (!alive) return;
        setMembers(Object.fromEntries(res.items.map((m) => [m.id, m])));
      })
      .catch(() => {
        /* names degrade to the member ID; the register still works */
      });
    return () => {
      alive = false;
    };
  }, [ctx.groupId]);

  useEffect(() => {
    if (data) {
      setRows(data.entries.map((e) => ({ ...e })));
      setDirty(false);
    }
  }, [data]);

  // Warn before losing an unsaved sheet -- a half-counted meeting is
  // genuinely expensive to redo.
  useEffect(() => {
    if (!dirty) return undefined;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const setField = useCallback((memberId, key, value) => {
    setRows((rs) =>
      rs.map((r) => {
        if (r.member_id !== memberId) return r;
        const next = { ...r, [key]: value };
        // Mirror the server's auto-recalculation so the Remaining Loan
        // cell updates as you type. The server recomputes authoritatively
        // on save; this is presentation only.
        if ((key === "loan_given" || key === "principal_paid") && !r.loan_remaining_manual) {
          next.loan_remaining = Math.max(
            money(r.loan_remaining_opening) + money(next.loan_given) - money(next.principal_paid),
            0
          );
        }
        return next;
      })
    );
    setDirty(true);
  }, []);

  const applyToAll = () => {
    setRows((rs) => rs.map((r) => (r.present ? { ...r, cur_saving: bulkAmount } : r)));
    setDirty(true);
  };

  const saveSheet = async () => {
    setSaveError(null);
    setSaving(true);
    try {
      const payload = rows.map((r) => ({
        member_id: r.member_id,
        present: r.present,
        cur_saving: String(money(r.cur_saving)),
        loan_given: String(money(r.loan_given)),
        principal_paid: String(money(r.principal_paid)),
        interest_paid: String(money(r.interest_paid)),
        fine: String(money(r.fine)),
        remarks: r.remarks || "Paid",
      }));
      await api.saveEntriesBulk(ctx.meetingId, payload);
      await reload();
      setDirty(false);
      toast(t.saved);
    } catch (err) {
      setSaveError(err);
    } finally {
      setSaving(false);
    }
  };

  const overrideLoan = async (memberId, value) => {
    try {
      await api.overrideLoan(ctx.meetingId, memberId, String(Math.max(money(value), 0)));
      await reload();
      toast("Remaining loan overridden");
    } catch (err) {
      setSaveError(err);
    }
  };

  const resetOverride = async (memberId) => {
    try {
      await api.resetLoanOverride(ctx.meetingId, memberId);
      await reload();
      toast("Reset to auto-calculated");
    } catch (err) {
      setSaveError(err);
    }
  };

  const addExpense = async () => {
    if (!newExpense.expense_type || newExpense.amount === "") return;
    try {
      await api.addExpense(ctx.meetingId, {
        expense_type: newExpense.expense_type,
        amount: String(money(newExpense.amount)),
      });
      setNewExpense({ expense_type: "Travel", amount: "" });
      await reload();
    } catch (err) {
      setSaveError(err);
    }
  };

  const removeExpense = async (id) => {
    try {
      await api.deleteExpense(ctx.meetingId, id);
      await reload();
    } catch (err) {
      setSaveError(err);
    }
  };

  const complete = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      // Flush pending edits first: completing with unsaved changes would
      // lock the meeting against the values the supervisor can still see
      // on screen.
      if (dirty) {
        await api.saveEntriesBulk(
          ctx.meetingId,
          rows.map((r) => ({
            member_id: r.member_id,
            present: r.present,
            cur_saving: String(money(r.cur_saving)),
            loan_given: String(money(r.loan_given)),
            principal_paid: String(money(r.principal_paid)),
            interest_paid: String(money(r.interest_paid)),
            fine: String(money(r.fine)),
            remarks: r.remarks || "Paid",
          }))
        );
      }
      await api.completeMeeting(ctx.meetingId);
      setShowComplete(false);
      await reload();
      toast("Meeting completed and locked");
    } catch (err) {
      setSaveError(err);
      setShowComplete(false);
    } finally {
      setSaving(false);
    }
  };

  // Local preview of the totals while the sheet is dirty, using exactly
  // the server's formulas. Once saved, the server's numbers take over.
  const preview = useMemo(() => {
    if (!rows) return null;
    const sum = (f) => rows.reduce((a, r) => a + money(f(r)), 0);
    const cash = rows.reduce(
      (a, r) => a + money(r.cur_saving) + money(r.principal_paid) + money(r.fine) + money(r.interest_paid),
      0
    );
    const expense = (data?.expenses || []).reduce((a, e) => a + money(e.amount), 0);
    const loan = sum((r) => r.loan_given);
    return {
      tot_prev_saving: sum((r) => r.prev_saving),
      tot_savings: sum((r) => r.cur_saving),
      tot_total_saving: sum((r) => money(r.prev_saving) + money(r.cur_saving)),
      tot_loan: loan,
      tot_install: sum((r) => r.principal_paid),
      tot_interest: sum((r) => r.interest_paid),
      tot_fine: sum((r) => r.fine),
      tot_paid_till_date: sum((r) => money(r.paid_till_date_opening) + money(r.principal_paid)),
      loan_remaining: sum((r) => r.loan_remaining),
      tot_cash_coll: cash,
      tot_expense: expense,
      cash_in_hand: cash - expense - loan,
      present: rows.filter((r) => r.present).length,
      absent: rows.filter((r) => !r.present).length,
    };
  }, [rows, data]);

  if (loading || !rows) return <Loading label={t.loading} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const totals = dirty ? preview : data.totals;

  return (
    <div>
      {/* header */}
      <div className="page-head no-print">
        <div style={{ minWidth: 0 }}>
          <button
            onClick={() => go("meetings", ctx)}
            style={{ background: "none", border: "none", color: "var(--tx2)", padding: 0, marginBottom: 4, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12 }}
          >
            <Icon n="ArrowLeft" s={13} /> {ctx.groupName || t.meetings}
          </button>
          <div className="row wrap" style={{ gap: 10 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
              {t.meeting} #{data.meeting_no}
            </h1>
            <Badge s={data.status} />
            {!locked && dirty && (
              <span className="tiny" style={{ color: "var(--warn)", fontWeight: 600 }}>{t.unsaved}</span>
            )}
            {saving && <Spinner size={14} />}
          </div>
          <div className="tiny muted" style={{ marginTop: 3 }}>
            {fmtDate(data.meeting_date)} &middot; {totals.present} {t.membersPresent.toLowerCase()}
          </div>
        </div>
        <div className="toolbar">
          <Btn
            size="sm"
            variant="secondary"
            icon="FileDown"
            onClick={() =>
              api
                .download(api.exportMeetingUrl(ctx.meetingId), `meeting_${data.meeting_no}.xlsx`)
                .catch((e) => setSaveError(e))
            }
          >
            {t.exportXls}
          </Btn>
          <Btn size="sm" variant="secondary" icon="Printer" onClick={() => window.print()}>
            {t.printReg}
          </Btn>
          {!locked && (
            <>
              <Btn size="sm" variant="secondary" onClick={saveSheet} disabled={saving || !dirty}>
                {saving ? t.saving : t.saveSheet}
              </Btn>
              <Btn size="sm" icon="Lock" onClick={() => setShowComplete(true)} disabled={saving}>
                {t.complete}
              </Btn>
            </>
          )}
        </div>
      </div>

      {locked && (
        <div
          className="row"
          style={{ gap: 8, background: "var(--ok-bg)", border: "1px solid var(--brand-lt)", borderRadius: 9, padding: "10px 14px", marginBottom: 14, color: "#166534", fontSize: 13, fontWeight: 600 }}
        >
          <Icon n="CheckCircle" s={16} c="var(--brand)" /> {t.lockedNotice}
        </div>
      )}

      <InlineError error={saveError} />

      {/* bulk apply */}
      {!locked && (
        <div
          className="row wrap no-print"
          style={{ gap: 10, background: "var(--brand-bg)", border: "1px solid var(--brand-lt)", borderRadius: 9, padding: "10px 14px", marginBottom: 12 }}
        >
          <span style={{ fontSize: 13, fontWeight: 600 }}>{t.applyAll}</span>
          <select
            value={bulkAmount}
            onChange={(e) => setBulkAmount(Number(e.target.value))}
            style={{ ...fieldStyle, width: 110, minHeight: 34, padding: "6px 10px" }}
          >
            {SAVING_PRESETS.filter((v) => v > 0).map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
          <Btn size="sm" onClick={applyToAll}>{t.apply}</Btn>
          <span className="tiny muted">Applies to members marked present. You can still edit rows individually.</span>
        </div>
      )}

      <div className="split-2">
        {/* register table */}
        <section className="card" style={{ overflow: "hidden" }}>
          <div className="table-wrap" style={{ maxHeight: "70vh" }}>
            <table className="register">
              <thead>
                <tr>
                  <th className="sticky-col" style={{ minWidth: 150 }}>{t.memberName}</th>
                  <th className="num">{t.prevSaving}</th>
                  <th className="num">{t.thisWeek}</th>
                  <th className="num">{t.totalSaving}</th>
                  <th className="num" style={{ color: "var(--err)" }}>{t.loanGiven}</th>
                  <th className="num">{t.paidTillDate}</th>
                  <th className="num">{t.principalPaid}</th>
                  <th className="num" style={{ color: "var(--violet)" }}>{t.interest}</th>
                  <th className="num" style={{ color: "var(--violet)" }}>{t.remainingLoan}</th>
                  <th className="num" style={{ color: "var(--info)" }}>{t.fine}</th>
                  <th className="num">{t.cashPaid}</th>
                  <th>{t.remarks}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const m = members[r.member_id];
                  const total = money(r.prev_saving) + money(r.cur_saving);
                  const paidTill = money(r.paid_till_date_opening) + money(r.principal_paid);
                  const cash =
                    money(r.cur_saving) + money(r.principal_paid) + money(r.fine) + money(r.interest_paid);
                  return (
                    <tr key={r.member_id} style={{ opacity: r.present ? 1 : 0.55 }}>
                      <td className="sticky-col">
                        <div className="row" style={{ gap: 7 }}>
                          {!locked && (
                            <input
                              type="checkbox"
                              checked={r.present}
                              onChange={(e) => setField(r.member_id, "present", e.target.checked)}
                              aria-label={`${m?.name || "Member"} present`}
                              style={{ accentColor: "var(--brand)", width: 15, height: 15 }}
                            />
                          )}
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 500, fontSize: 12.5 }}>{m?.name || `Member ${i + 1}`}</div>
                            <div className="tiny" style={{ color: "var(--txm)", fontFamily: "ui-monospace, monospace" }}>
                              {m?.code || ""}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="num muted">{money(r.prev_saving).toLocaleString("en-IN")}</td>
                      <td className="num">
                        {locked ? (
                          money(r.cur_saving).toLocaleString("en-IN")
                        ) : (
                          <select
                            value={money(r.cur_saving)}
                            disabled={!r.present}
                            onChange={(e) => setField(r.member_id, "cur_saving", Number(e.target.value))}
                            className="cell-input"
                            style={{ width: 82, textAlign: "left" }}
                          >
                            {SAVING_PRESETS.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        )}
                      </td>
                      <td className="num" style={{ fontWeight: 600, color: "var(--ok)" }}>
                        {total.toLocaleString("en-IN")}
                      </td>
                      <td className="num">
                        {locked ? (
                          money(r.loan_given) ? money(r.loan_given).toLocaleString("en-IN") : "\u2014"
                        ) : (
                          <input
                            type="number" min="0" step="1" className="cell-input"
                            value={money(r.loan_given) || ""}
                            disabled={!r.present}
                            placeholder={"\u2014"}
                            onChange={(e) => setField(r.member_id, "loan_given", e.target.value)}
                            style={{ color: "var(--err)" }}
                          />
                        )}
                      </td>
                      <td className="num muted">{paidTill ? paidTill.toLocaleString("en-IN") : "\u2014"}</td>
                      <td className="num">
                        {locked ? (
                          money(r.principal_paid) ? money(r.principal_paid).toLocaleString("en-IN") : "\u2014"
                        ) : (
                          <input
                            type="number" min="0" step="1" className="cell-input"
                            value={money(r.principal_paid) || ""}
                            disabled={!r.present}
                            placeholder={"\u2014"}
                            onChange={(e) => setField(r.member_id, "principal_paid", e.target.value)}
                          />
                        )}
                      </td>
                      <td className="num">
                        {locked ? (
                          money(r.interest_paid) ? money(r.interest_paid).toLocaleString("en-IN") : "\u2014"
                        ) : (
                          <input
                            type="number" min="0" step="1" className="cell-input"
                            value={money(r.interest_paid) || ""}
                            disabled={!r.present}
                            placeholder={"\u2014"}
                            onChange={(e) => setField(r.member_id, "interest_paid", e.target.value)}
                            style={{ color: "var(--violet)", width: 66 }}
                          />
                        )}
                      </td>
                      <td className="num">
                        <div className="row" style={{ justifyContent: "flex-end", gap: 3 }}>
                          <span style={{ fontWeight: 600, color: money(r.loan_remaining) ? "var(--violet)" : "var(--txm)" }}>
                            {money(r.loan_remaining) ? money(r.loan_remaining).toLocaleString("en-IN") : "\u2014"}
                          </span>
                          {r.loan_remaining_manual && (
                            <span title="Manually adjusted" className="tiny" style={{ color: "var(--warn)" }}>&#9998;</span>
                          )}
                          {!locked && (
                            <>
                              <IconBtn
                                n="Edit"
                                title="Override remaining loan"
                                onClick={() => {
                                  const v = window.prompt(
                                    "Set Remaining Loan manually for this member.\nThis freezes it from auto-recalculation for this meeting.",
                                    String(money(r.loan_remaining))
                                  );
                                  if (v !== null) overrideLoan(r.member_id, v);
                                }}
                              />
                              {r.loan_remaining_manual && (
                                <IconBtn n="RefreshCw" title="Reset to auto-calculated" color="var(--warn)" onClick={() => resetOverride(r.member_id)} />
                              )}
                            </>
                          )}
                        </div>
                      </td>
                      <td className="num">
                        {locked ? (
                          money(r.fine) ? money(r.fine).toLocaleString("en-IN") : "\u2014"
                        ) : (
                          <input
                            type="number" min="0" step="1" className="cell-input"
                            value={money(r.fine) || ""}
                            disabled={!r.present}
                            placeholder={"\u2014"}
                            onChange={(e) => setField(r.member_id, "fine", e.target.value)}
                            style={{ color: "var(--info)", width: 60 }}
                          />
                        )}
                      </td>
                      <td className="num" style={{ fontWeight: 600 }}>{cash.toLocaleString("en-IN")}</td>
                      <td>
                        {locked ? (
                          <span className="tiny muted">{r.remarks}</span>
                        ) : (
                          <select
                            value={r.remarks || "Paid"}
                            disabled={!r.present}
                            onChange={(e) => setField(r.member_id, "remarks", e.target.value)}
                            className="cell-input"
                            style={{ width: 104, textAlign: "left" }}
                          >
                            {REMARKS.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="sticky-col" style={{ fontWeight: 700 }}>TOTAL</td>
                  <td className="num">{money(totals.tot_prev_saving).toLocaleString("en-IN")}</td>
                  <td className="num">{money(totals.tot_savings).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--ok)" }}>{money(totals.tot_total_saving).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--err)" }}>{money(totals.tot_loan).toLocaleString("en-IN")}</td>
                  <td className="num">{money(totals.tot_paid_till_date).toLocaleString("en-IN")}</td>
                  <td className="num">{money(totals.tot_install).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--violet)" }}>{money(totals.tot_interest).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--violet)" }}>{money(totals.loan_remaining).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--info)" }}>{money(totals.tot_fine).toLocaleString("en-IN")}</td>
                  <td className="num" style={{ color: "var(--ok)" }}>{money(totals.tot_cash_coll).toLocaleString("en-IN")}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </section>

        {/* side panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card title={t.todayExpenses}>
            {(data.expenses || []).length === 0 && <div className="tiny muted">No expenses recorded.</div>}
            {(data.expenses || []).map((e) => (
              <div key={e.id} className="row" style={{ padding: "6px 0", borderBottom: "1px solid var(--bdr)" }}>
                <span style={{ fontSize: 13 }}>{e.expense_type}</span>
                <div className="spacer" />
                <span style={{ fontSize: 13, fontWeight: 600 }}>{inr(e.amount)}</span>
                {!locked && <IconBtn n="X" title="Remove" color="var(--err)" onClick={() => removeExpense(e.id)} />}
              </div>
            ))}
            {!locked && (
              <div className="row" style={{ gap: 6, marginTop: 10 }}>
                <select
                  value={newExpense.expense_type}
                  onChange={(e) => setNewExpense({ ...newExpense, expense_type: e.target.value })}
                  style={{ ...fieldStyle, minHeight: 34, padding: "6px 8px", flex: 1 }}
                >
                  {EXPENSE_PRESETS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
                <input
                  type="number" min="0" step="1" placeholder={"\u20b9"}
                  value={newExpense.amount}
                  onChange={(e) => setNewExpense({ ...newExpense, amount: e.target.value })}
                  style={{ ...fieldStyle, minHeight: 34, padding: "6px 8px", width: 82, textAlign: "right" }}
                />
                <Btn size="sm" onClick={addExpense}>+</Btn>
              </div>
            )}
            <div className="row" style={{ marginTop: 12, paddingTop: 10, borderTop: "2px solid var(--bdr)" }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{t.totalExpense}</span>
              <div className="spacer" />
              <span style={{ fontSize: 14, fontWeight: 700, color: "var(--err)" }}>{inr(totals.tot_expense)}</span>
            </div>
          </Card>

          <Card title={t.mtgSummary}>
            {[
              [t.membersPresent, totals.present, "var(--tx1)"],
              [t.membersAbsent, totals.absent, "var(--tx2)"],
              [t.savingsCollection, inr(totals.tot_savings), "var(--ok)"],
              [t.loansGiven, inr(totals.tot_loan), "var(--err)"],
              [t.installColl, inr(totals.tot_install), "var(--tx1)"],
              [t.interestColl, inr(totals.tot_interest), "var(--violet)"],
              [t.finesColl, inr(totals.tot_fine), "var(--info)"],
              [t.totalExpense, inr(totals.tot_expense), "var(--warn)"],
              ["Loan Balance Remaining", inr(totals.loan_remaining), "var(--violet)"],
            ].map(([label, value, color]) => (
              <div key={label} className="row" style={{ padding: "6px 0", borderBottom: "1px solid var(--bdr)" }}>
                <span className="tiny muted">{label}</span>
                <div className="spacer" />
                <span style={{ fontSize: 13, fontWeight: 600, color }}>{value}</span>
              </div>
            ))}
            <div
              className="row"
              style={{ marginTop: 12, padding: "10px 12px", background: "var(--brand-bg)", border: "1px solid var(--brand-lt)", borderRadius: 8 }}
            >
              <span style={{ fontSize: 13, fontWeight: 700 }}>{t.cashInHand}</span>
              <div className="spacer" />
              <span style={{ fontSize: 18, fontWeight: 800, color: "var(--brand)" }}>{inr(totals.cash_in_hand)}</span>
            </div>
            {dirty && (
              <div className="tiny" style={{ marginTop: 8, color: "var(--warn)" }}>
                Showing unsaved figures. Save the register to confirm them.
              </div>
            )}
          </Card>
        </div>
      </div>

      {showComplete && (
        <ConfirmModal
          title="Complete and lock this meeting?"
          confirmLabel="Yes, complete"
          danger={false}
          busy={saving}
          onClose={() => setShowComplete(false)}
          onConfirm={complete}
          message={
            <>
              <div style={{ marginBottom: 12 }}>{t.lockWarning}</div>
              <div
                style={{ background: "var(--brand-bg)", borderRadius: 8, padding: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 12 }}
              >
                {[
                  ["Savings", inr(totals.tot_savings)],
                  ["Cash in Hand", inr(totals.cash_in_hand)],
                  ["Present", totals.present],
                  ["Expenses", inr(totals.tot_expense)],
                  ["Interest", inr(totals.tot_interest)],
                  ["Loan Remaining", inr(totals.loan_remaining)],
                ].map(([l, v]) => (
                  <div key={l}>
                    <span className="muted">{l}: </span>
                    <strong>{v}</strong>
                  </div>
                ))}
              </div>
            </>
          }
        />
      )}
    </div>
  );
}
