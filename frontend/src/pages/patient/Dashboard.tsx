import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { AssessmentRecord, Dashboard as DashboardData, Measurement } from "../../api/types";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PALETTE, TrendChart } from "../../components/charts";
import { bloodPressure, cholesterol, glucose, LEVEL_SCORE } from "../../components/status";
import { Card, EmptyState, ErrorState, LevelBadge, Notice, Skeleton, Stat, day, when } from "../../components/ui";

export default function Dashboard() {
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardData>("/me/dashboard") });
  const history = useQuery({ queryKey: ["assessments"], queryFn: () => api<AssessmentRecord[]>("/me/assessments") });
  const readings = useQuery({ queryKey: ["measurements"], queryFn: () => api<Measurement[]>("/me/measurements") });
  if (isLoading) return <div className="stack"><Skeleton lines={2} height={26} /><div className="stats">{[0, 1, 2, 3].map((i) => <div key={i} className="stat"><Skeleton lines={2} /></div>)}</div></div>;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  const m = data.latest_measurements;
  const bp = m.systolic && m.diastolic ? `${Math.round(m.systolic)}/${Math.round(m.diastolic)}` : m.systolic ? `${Math.round(m.systolic)}` : "None yet";
  return (
    <div className="stack">
      <div>
        <h1>Hello, {data.user.full_name.split(" ")[0]}</h1>
        <p className="muted">Your heart-health overview. Nothing here is a diagnosis.</p>
      </div>
      {!data.user.profile_complete && (
        <Notice tone="info" title="Complete your profile">
          Assessments need your sex, birth year and smoking status. <Link to="/app/profile">Update your profile</Link>.
        </Notice>
      )}
      <div className="stats">
        <Stat label="Assessments" value={data.total_assessments} />
        <Stat label="Blood pressure" value={bp} hint="mmHg, latest" status={bloodPressure(m.systolic, m.diastolic)} />
        <Stat label="Cholesterol" value={m.cholesterol ? Math.round(m.cholesterol) : "None yet"} hint="mg/dL, latest" status={cholesterol(m.cholesterol)} />
        <Stat label="Fasting glucose" value={m.glucose ? Math.round(m.glucose) : "None yet"} hint="mg/dL, latest" status={glucose(m.glucose)} />
      </div>
      <div className="actions">
        <Link className="btn primary" to="/app/symptoms">Check symptoms</Link>
        <Link className="btn ghost" to="/app/wellness">Review risk factors</Link>
        <Link className="btn ghost" to="/app/measurements">Add a measurement</Link>
      </div>
      <div className="grid2">
        <Card title="Blood pressure trend" action={<Link to="/app/measurements">Details</Link>}>
          {readings.isLoading ? <Skeleton lines={4} height={30} /> : (() => {
            const rows = (readings.data ?? []).filter((r) => r.kind === "systolic");
            return rows.length < 2 ? <EmptyState title="Add two readings to see a trend">Log your blood pressure from the Measurements page.</EmptyState> : <TrendChart rows={rows} unit="mmHg" />;
          })()}
        </Card>
        <Card title="Urgency over time">
          {history.isLoading ? <Skeleton lines={4} height={30} /> : (() => {
            const rows = [...(history.data ?? [])].reverse().map((a) => ({ t: new Date(a.created_at).getTime(), score: LEVEL_SCORE[a.urgency] }));
            return rows.length < 2 ? <EmptyState title="Your assessments will chart here">After two assessments you can see whether things are improving.</EmptyState> : (
              <div className="chart-box" role="img" aria-label="Assessment urgency over time">
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                    <CartesianGrid stroke="#e3eaec" />
                    <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={{ fontSize: 12 }} tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })} />
                    <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} width={86} tick={{ fontSize: 12 }} tickFormatter={(v) => ["", "Routine", "Soon", "Days", "Same day", "Emergency"][v]} />
                    <Tooltip labelFormatter={(v) => new Date(v as number).toLocaleDateString()} formatter={(v) => [["", "Routine", "See a doctor soon", "Within days", "Same day", "Emergency"][Number(v)], "Urgency"]} />
                    <Line type="stepAfter" dataKey="score" stroke={PALETTE[1]} strokeWidth={2.2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            );
          })()}
        </Card>
      </div>
      <div className="grid2">
        <Card title="Recent assessments" action={<Link to="/app/assessments">All</Link>}>
          {data.recent.length === 0 ? <EmptyState title="No assessments yet">Start with a symptom check or a wellness review.</EmptyState> : (
            <ul className="list">
              {data.recent.map((a) => (
                <li key={a.id}>
                  <Link to={`/app/assessments/${a.id}`}><strong>{a.headline}</strong><span className="muted small">{when(a.created_at)} · {a.kind}</span></Link>
                  <LevelBadge level={a.urgency} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Upcoming appointments" action={<Link to="/app/appointments">Manage</Link>}>
          {data.upcoming.length === 0 ? <EmptyState title="Nothing scheduled">{data.user.clinic ? "Request an appointment with your clinic." : "Join a clinic from your profile to request appointments."}</EmptyState> : (
            <ul className="list">
              {data.upcoming.map((a) => <li key={a.id}><div><strong>{a.reason}</strong><span className="muted small">{day(a.scheduled_at)}{a.clinician ? ` · ${a.clinician}` : ""}</span></div><span className="badge">{a.status}</span></li>)}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
