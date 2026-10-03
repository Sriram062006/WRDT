import { useRef, useState } from "react";

import { api } from "../lib/api.js";
import { inr } from "../lib/format.js";
import { Card, TableCard } from "../components/Card.jsx";
import { Badge, Btn, InlineError, PageHead, Spinner } from "../components/ui.jsx";

/**
 * Excel import.
 *
 * The prototype parsed the workbook in the browser with SheetJS and
 * pushed rows into in-memory arrays -- nothing reached a database, and
 * the library it used carries two unfixed high-severity advisories with
 * no patched release. Parsing now happens server-side with openpyxl, so
 * the dependency is gone from the frontend entirely and preview/commit
 * share one code path on the server.
 */
export default function ExcelImport({ t, toast }) {
  const fileRef = useRef(null);
  const [step, setStep] = useState("upload");
  const [fileName, setFileName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);

  const reset = () => {
    setStep("upload"); setFileName(""); setError(null);
    setPreview(null); setResult(null);
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const body = await api.importPreview(file);
      setPreview(body);
      setFileName(file.name);
      setStep("preview");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = await api.importCommit(preview.batch_id);
      setResult(body.summary);
      setStep("done");
      toast("Import complete");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const Chip = ({ label, value, color }) => (
    <div style={{ background: "#f8fafc", border: "1px solid var(--bdr)", borderRadius: 8, padding: "10px 14px", minWidth: 118 }}>
      <div className="tiny muted">{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || "var(--tx1)" }}>{value}</div>
    </div>
  );

  return (
    <div>
      <PageHead
        title={t.excelImport}
        sub="Bring an existing Sangam register into WRDT: regions, groups and members."
        actions={
          <Btn
            variant="secondary"
            icon="FileDown"
            onClick={() => api.download(api.importTemplateUrl(), "wrdt_import_template.xlsx").catch(setError)}
          >
            {t.downloadTemplate}
          </Btn>
        }
      />

      <InlineError error={error} />

      {step === "upload" && (
        <Card>
          <div style={{ border: "2px dashed var(--bdr)", borderRadius: 10, padding: "40px 20px", textAlign: "center" }}>
            <Btn icon="Upload" onClick={() => fileRef.current?.click()} disabled={busy}>
              {busy ? "Reading..." : t.uploadFile}
            </Btn>
            <input ref={fileRef} type="file" accept=".xlsx,.xlsm" onChange={onFile} style={{ display: "none" }} />
            <div className="tiny muted" style={{ marginTop: 12, lineHeight: 1.7 }}>
              Required columns: <strong>Region</strong>, <strong>Group</strong>, <strong>Member Name</strong>.
              <br />
              <strong>Previous Savings</strong> is optional.
              <br />
              Nothing is written until you review the preview and confirm.
            </div>
          </div>
        </Card>
      )}

      {step === "preview" && preview && (
        <>
          <Card>
            <div className="row wrap" style={{ marginBottom: 14, gap: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{fileName}</div>
              <div className="spacer" />
              <Btn variant="secondary" size="sm" onClick={reset} disabled={busy}>{t.cancel}</Btn>
              <Btn size="sm" onClick={commit} disabled={busy || preview.summary.members_created === 0}>
                {busy ? <Spinner size={13} /> : t.importNow}
              </Btn>
            </div>
            <div className="row wrap" style={{ gap: 10 }}>
              <Chip label={t.rowsTotal} value={preview.summary.total} />
              <Chip label={t.newRegions} value={preview.summary.regions_created} color="var(--brand)" />
              <Chip label={t.newGroups} value={preview.summary.groups_created} color="var(--brand)" />
              <Chip label={t.newMembers} value={preview.summary.members_created} color="var(--brand)" />
              <Chip label={t.duplicatesSkipped} value={preview.summary.members_skipped} />
              <Chip
                label={t.invalidRows}
                value={preview.summary.invalid_rows}
                color={preview.summary.invalid_rows ? "var(--err)" : undefined}
              />
            </div>
            <div className="tiny muted" style={{ marginTop: 12 }}>
              This is a dry run. Nothing has been saved yet.
            </div>
          </Card>

          <div style={{ height: 14 }} />

          <TableCard>
            <table className="data">
              <thead>
                <tr>
                  <th>{t.region}</th>
                  <th>{t.group}</th>
                  <th>{t.memberName}</th>
                  <th className="num">{t.prevSavings}</th>
                  <th>{t.status}</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.region || "\u2014"}</td>
                    <td>{r.group || "\u2014"}</td>
                    <td>{r.member || "\u2014"}</td>
                    <td className="num muted">{r.prev_saving === null ? "\u2014" : inr(r.prev_saving)}</td>
                    <td><Badge s={r.status} /></td>
                    <td className="tiny muted">{r.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
        </>
      )}

      {step === "done" && result && (
        <Card>
          <div style={{ textAlign: "center", padding: "10px 0 20px" }}>
            <div
              style={{
                width: 54, height: 54, borderRadius: 14, background: "var(--ok-bg)",
                display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 10,
              }}
            >
              <span style={{ fontSize: 26 }}>&#10003;</span>
            </div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{t.importComplete}</div>
            <div className="tiny muted" style={{ marginTop: 4 }}>
              These records now appear in Regions, Groups and Members.
            </div>
          </div>
          <div className="row wrap" style={{ gap: 10, justifyContent: "center", marginBottom: 18 }}>
            <Chip label={t.newRegions} value={result.regions_created} color="var(--brand)" />
            <Chip label={t.newGroups} value={result.groups_created} color="var(--brand)" />
            <Chip label={t.newMembers} value={result.members_created} color="var(--brand)" />
            <Chip label={t.duplicatesSkipped} value={result.members_skipped} />
            <Chip label={t.invalidRows} value={result.invalid_rows} color={result.invalid_rows ? "var(--err)" : undefined} />
          </div>
          <div style={{ textAlign: "center" }}>
            <Btn icon="Upload" onClick={reset}>{t.importAnother}</Btn>
          </div>
        </Card>
      )}
    </div>
  );
}
