import { useEffect, useMemo, useState } from 'react';
const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const fmt = n => Number(n || 0).toLocaleString('en-IN');
export default function App() {
  const [summary,setSummary]=useState(null), [cases,setCases]=useState([]), [status,setStatus]=useState('OPEN');
  const [health,setHealth]=useState('Checking API…'), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  async function load(){setBusy(true);setError('');try{
    const [h,s,c]=await Promise.all([fetch(`${API}/health`),fetch(`${API}/api/v1/dashboard/summary`),fetch(`${API}/api/v1/cases?case_status=${status}`)]);
    if(!h.ok||!s.ok||!c.ok)throw new Error('API request failed. Check backend and database.');
    const [hd,sd,cd]=await Promise.all([h.json(),s.json(),c.json()]);setHealth(`${hd.status.toUpperCase()} · ${hd.application}`);setSummary(sd);setCases(cd);
  }catch(e){setError(e.message);setHealth('Backend unavailable');}finally{setBusy(false);}}
  useEffect(()=>{load();},[status]);
  const high=useMemo(()=>cases.filter(x=>x.priority_band==='HIGH').length,[cases]);
  const metrics=[['Customers',summary?.customers],['Accounts',summary?.accounts],['Loans',summary?.loans],['Installments',summary?.installments],['Payments',summary?.payments],['Open cases',summary?.open_cases],['On hold',summary?.on_hold_cases],['Open exceptions',summary?.open_exceptions]];
  return <div className="app-shell"><header className="topbar"><div><div className="eyebrow">YOTTAFLEX AI · OPERATIONS CONSOLE</div><h1>Smart Collections</h1><p>Responsible delinquency prioritization & compliance monitoring</p></div><div className="health"><span className="pulse"/>{health}</div></header>
    {error&&<div className="alert">{error}</div>}
    <section className="section-head"><div><h2>Portfolio overview</h2><p>Live counts from the connected PostgreSQL database</p></div><button onClick={load} disabled={busy}>{busy?'Refreshing…':'Refresh data'}</button></section>
    <section className="metrics">{metrics.map(([label,value])=><article className="metric" key={label}><span>{label}</span><strong>{summary?fmt(value):'—'}</strong></article>)}</section>
    <section className="panel"><div className="section-head"><div><h2>Collection work queue</h2><p>{cases.length} cases returned · {high} high-priority in this view</p></div><select value={status} onChange={e=>setStatus(e.target.value)}><option>OPEN</option><option>ON_HOLD</option><option>RESOLVED</option><option>CLOSED</option></select></div>
      <div className="table-wrap"><table><thead><tr><th>Case ID</th><th>Loan ID</th><th>Priority</th><th>Score</th><th>Status</th></tr></thead><tbody>{cases.slice(0,100).map(x=><tr key={x.case_id}><td>{x.case_id}</td><td>{x.loan_id}</td><td><span className={`tag ${String(x.priority_band).toLowerCase()}`}>{x.priority_band}</span></td><td>{Number(x.priority_score).toFixed(2)}</td><td>{x.case_status}</td></tr>)}{!cases.length&&<tr><td colSpan="5" className="empty">No cases in this status.</td></tr>}</tbody></table></div><div className="footnote">Showing up to 100 cases. Ground-truth labels are kept outside operational scoring.</div></section>
    <footer>YottaFlex Smart Collections · Synthetic data only · Contact restrictions enforced before outreach.</footer></div>;
}
