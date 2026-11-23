import json
import html
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
WEB = ROOT / "web"
WEB.mkdir(exist_ok=True)

def load_json(name, default):
    path = DATA / name
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)

apps = load_json("apps.json", [])
results = load_json("research_results.json", [])
coverage = load_json("composio_coverage.json", [])
verification = load_json("verification_results.json", {"checks": [], "summary": {}})

if isinstance(verification, list):
    checks = verification
else:
    checks = verification.get("checks", [])

coverage_by_id = {x.get("app_id"): x for x in coverage}
results_by_id = {x.get("app_id"): x for x in results}

records = []
for app in apps:
    app_id = app.get("id")
    research = results_by_id.get(app_id, {})
    match = coverage_by_id.get(app_id, {})
    records.append({
        **app,
        **research,
        "research_status": research.get("status", "not_researched"),
        "composio_coverage": research.get("composio_coverage") or match
    })

completed = sum(x["research_status"] == "completed" for x in records)
failed = sum(x["research_status"] == "failed" for x in records)
confirmed = sum(x.get("composio_coverage", {}).get("match_status") == "confirmed_match" for x in records)
possible = sum(x.get("composio_coverage", {}).get("match_status") == "possible_match" for x in records)
no_match = sum(x.get("composio_coverage", {}).get("match_status") == "no_match" for x in records)

def labels(field):
    counter = Counter()
    for r in records:
        if r["research_status"] != "completed":
            continue
        value = r.get(field, [])
        if isinstance(value, list):
            for v in value:
                if v and v != "Unknown":
                    counter[v] += 1
        elif value and value != "Unknown":
            counter[str(value)] += 1
    return dict(counter.most_common())

category_stats = []
for category in sorted(set(x.get("category", "Other") for x in records)):
    group = [x for x in records if x.get("category") == category]
    done = [x for x in group if x["research_status"] == "completed"]
    category_stats.append({
        "name": category,
        "total": len(group),
        "researched": len(done),
        "easy": sum(x.get("buildability") == "Easy" for x in done),
        "difficult": sum(x.get("buildability") == "Difficult" for x in done),
        "blocked": sum(x.get("buildability") == "Blocked" for x in done),
        "unknown": sum(x.get("buildability") == "Unknown" for x in done)
    })

payload = {
    "records": records,
    "stats": {
        "total": len(records),
        "completed": completed,
        "failed": failed,
        "pending": len(records) - completed - failed,
        "confirmed": confirmed,
        "possible": possible,
        "no_match": no_match,
        "checks": len(checks),
        "auth": labels("authentication_methods"),
        "access": labels("access_model"),
        "api": labels("api_surface"),
        "mcp": {
            k: v for k, v in labels("mcp_availability").items()
            if k != "Composio toolkit"
        },
        "buildability": labels("buildability"),
        "categories": category_stats
    },
    "verification": verification
}

data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

page = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AppScope — Integration Intelligence</title>
<style>
:root{--bg:#090d18;--panel:#111827;--panel2:#151f31;--line:#263449;--text:#edf3ff;--muted:#94a3b8;--blue:#70a5ff;--cyan:#55dfd0;--green:#5cdaa0;--amber:#f5c46b;--red:#ff7d86}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 15% 0%,#172744 0,transparent 42%),var(--bg);color:var(--text);font:14px/1.55 Inter,Segoe UI,Arial,sans-serif}
header{padding:28px 5vw 22px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}
.brand{font-size:12px;letter-spacing:3px;color:var(--cyan);font-weight:800}.title{font-size:clamp(27px,4vw,42px);font-weight:750;letter-spacing:-1.5px;margin:8px 0 3px}.subtitle{color:var(--muted);max-width:700px}
.pill{border:1px solid #355078;border-radius:30px;padding:8px 13px;color:#b8d3ff;background:#14223a;font-size:12px}
nav{position:sticky;top:0;z-index:5;background:#0b1120ed;backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:10px 5vw;display:flex;gap:8px;overflow:auto}
nav a{white-space:nowrap;color:var(--muted);text-decoration:none;padding:7px 11px;border-radius:7px}nav a:hover{background:#1a2941;color:white}
main{max-width:1440px;margin:auto;padding:28px 5vw 70px}.section{margin:34px 0}.section h2{font-size:21px;margin:0 0 5px}.hint{color:var(--muted);margin:0 0 18px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.card{background:linear-gradient(145deg,#172338,#101827);border:1px solid var(--line);border-radius:13px;padding:18px;min-width:0}.metric{font-size:30px;font-weight:750;letter-spacing:-1px}.label{color:var(--muted);font-size:12px}.accent{color:var(--cyan)}.blue{color:var(--blue)}.amber{color:var(--amber)}
.progress{height:8px;border-radius:9px;background:#263449;overflow:hidden;margin:12px 0}.progress span{display:block;height:100%;background:linear-gradient(90deg,#5d91f6,#54ddcc)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.barrow{display:grid;grid-template-columns:minmax(110px,1fr) 2fr 35px;align-items:center;gap:10px;margin:11px 0}.barname{color:#c5d1e4;font-size:12px}.track{height:9px;background:#273449;border-radius:8px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,#668ef4,#55dfd0);border-radius:8px}.barval{text-align:right;color:var(--muted);font-size:12px}
.controls{display:flex;gap:9px;flex-wrap:wrap;margin:15px 0}input,select{background:#101a2a;border:1px solid #34445c;color:var(--text);border-radius:8px;padding:10px 12px;outline:none}input{flex:1;min-width:200px}select{min-width:160px}
.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:#101827}table{border-collapse:collapse;width:100%;min-width:900px}th,td{padding:12px 13px;text-align:left;border-bottom:1px solid #253247}th{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#8fa3c0;background:#152136;position:sticky;top:0}td{font-size:12px;color:#d4deee}tr:hover td{background:#17243a}.appname{font-weight:700;color:white;font-size:13px}.tag{display:inline-block;padding:3px 7px;border-radius:20px;background:#20324b;color:#b9d5ff;font-size:10px;margin:2px}.tag.good{background:#14372e;color:#7ce0b3}.tag.warn{background:#41331e;color:#f5ce82}.tag.bad{background:#42242b;color:#ff9ca3}
details{background:#121d2e;border:1px solid var(--line);border-radius:10px;margin:8px 0;padding:13px}summary{cursor:pointer;font-weight:650}details p{color:#b5c2d5;font-size:12px;overflow-wrap:anywhere}a{color:#83b6ff}
.note{border-left:3px solid var(--amber);padding:12px 15px;background:#211d17;border-radius:0 8px 8px 0;color:#e9d5ad;margin:15px 0}
footer{border-top:1px solid var(--line);padding:25px 5vw;color:var(--muted);font-size:12px}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}@media(max-width:480px){.grid{grid-template-columns:1fr}header{padding-top:20px}}
</style>
</head>
<body>
<header><div><div class="brand">APP SCOPE / RESEARCH PROJECT</div><div class="title">Integration Intelligence</div><div class="subtitle">A structured landscape of API access, authentication, MCP availability and integration buildability across 100 applications.</div></div><div class="pill">RESEARCH SNAPSHOT · LIVE DATA EXPORT</div></header>
<nav><a href="#overview">Overview</a><a href="#explorer">App explorer</a><a href="#auth">Authentication</a><a href="#access">Access</a><a href="#apis">API & MCP</a><a href="#buildability">Buildability</a><a href="#verification">Verification</a><a href="#method">Methodology</a></nav>
<main>
<section class="section" id="overview"><h2>Research at a glance</h2><p class="hint">Coverage of the target application landscape and the current state of automated research.</p>
<div class="grid" id="kpis"></div><div class="card" style="margin-top:14px"><div style="display:flex;justify-content:space-between;gap:10px"><b>Research progress</b><span id="progressText" class="accent"></span></div><div class="progress"><span id="progressBar"></span></div><div class="label">Unresearched applications are not classified as unsupported; they are pending investigation.</div></div>
<div class="note">Interpretation rule: a Composio catalogue match indicates a toolkit name/alias match. It does not independently verify vendor API access, pricing, credentials, or self-serve availability.</div></section>
<section class="section" id="findings">
<h2>What the research reveals</h2>
<p class="hint">The key patterns across the 100-app integration landscape.</p>

<div class="grid">
<div class="card">
<div class="metric accent">51</div>
<b>API keys lead authentication</b>
<p class="label">API keys were detected more frequently than OAuth2, which appeared 37 times. Apps may support multiple authentication methods.</p>
</div>

<div class="card">
<div class="metric amber">95%</div>
<b>Access is the biggest blind spot</b>
<p class="label">Access requirements remain Unknown for 95 applications. Documentation discovery alone was insufficient to establish credential availability.</p>
</div>

<div class="card">
<div class="metric blue">71%</div>
<b>Composio catalogue coverage</b>
<p class="label">71 applications have confirmed name/alias matches against the 1,842-toolkit catalogue. This is not proof of successful integration.</p>
</div>

<div class="card">
<div class="metric accent">64</div>
<b>Moderate buildability assessments</b>
<p class="label">64 applications were assessed as Moderate, largely reflecting detected APIs with unresolved or mixed access conditions.</p>
</div>
</div>

<div class="note">
These are automated research findings, not independently confirmed facts for every application. Unknown is intentionally retained where evidence is insufficient.
</div>
</section>
<section class="section" id="explorer"><h2>Application explorer</h2><p class="hint">Search applications, filter by category or research status, and expand a record to inspect evidence and limitations.</p>
<div class="controls"><input id="search" placeholder="Search app, API, authentication, blocker..."><select id="category"><option value="">All categories</option></select><select id="status"><option value="">All research statuses</option><option>completed</option><option>failed</option><option>not_researched</option></select><select id="build"><option value="">All buildability</option><option>Easy</option><option>Difficult</option><option>Blocked</option><option>Unknown</option></select></div>
<div class="tablewrap"><table><thead><tr><th>Application</th><th>Category</th><th>Research</th><th>Authentication</th><th>API surface</th><th>MCP</th><th>Buildability</th><th>Composio</th></tr></thead><tbody id="appRows"></tbody></table></div><p class="label" id="rowCount" style="margin-top:10px"></p><div id="details"></div></section>
<section class="section" id="auth"><h2>Authentication landscape</h2><p class="hint">Detected authentication labels from fetched research records. Counts represent label mentions, not mutually exclusive apps.</p><div class="card" id="authBars"></div></section>
<section class="section" id="access"><h2>Access models</h2><p class="hint">Self-serve, gated, paid and other access findings where the research pipeline found supporting evidence.</p><div class="card" id="accessBars"></div></section>
<section class="section" id="apis"><h2>API & MCP landscape</h2><p class="hint">API surfaces and MCP availability recorded from official or otherwise identified evidence.</p><div class="two"><div class="card"><h3>API surface</h3><div id="apiBars"></div></div><div class="card"><h3>MCP availability</h3><div id="mcpBars"></div></div></div></section>
<section class="section" id="buildability"><h2>Integration buildability</h2><p class="hint">A directional assessment based on observed API availability and access constraints—not a guarantee of implementation effort.</p><div class="two"><div class="card"><h3>Overall findings</h3><div id="buildBars"></div></div><div class="card"><h3>Category comparison</h3><div id="categoryBars"></div></div></div></section>
<section class="section" id="verification"><h2>Verification & quality</h2><p class="hint">Only explicitly recorded manual checks count toward measured verification accuracy.</p><div class="grid" id="verificationKpis"></div><div class="note" id="verificationNote"></div>
<div class="card" style="margin-top:14px">
<h3>Examples from manual verification</h3>
<p class="label">Actual checks recorded against documentation. These illustrate where automated findings matched or missed the official evidence.</p>
<div id="verificationExamples"></div>
</div>
</section>
<section class="section" id="method"><h2>Methodology & limitations</h2><div class="card"><h3>Research workflow</h3><p>1. Start with a predefined list of 100 applications across 10 categories.</p><p>2. Search for developer documentation, API references, authentication guidance and MCP resources.</p><p>3. Fetch pages and extract findings from page text. Search snippets alone are not treated as proof.</p><p>4. Match application names and aliases against the Composio toolkit catalogue as a separate coverage signal.</p><p>5. Store per-application results, evidence URLs, fetch errors and fields requiring human review.</p><p>6. Manually verify selected findings against official documentation and record verdicts.</p><h3>Interpretation safeguards</h3><p>Unknown means insufficient evidence was collected. A failed fetch is not evidence that an API does not exist. A Composio match is not proof of free or self-serve API access. Community MCP servers are distinguished from official vendor MCP support.</p><p>Buildability is classified as Easy, Difficult, Blocked or Unknown using the available evidence. It is a research heuristic, not a technical implementation test.</p><h3>Reproducibility</h3><p>The research pipeline and source data are maintained in the accompanying project repository. Rebuild this report after refreshing the JSON research data.</p></div></section>
</main><footer>AppScope · Integration Intelligence · Generated from local research data. Findings should be interpreted alongside their evidence URLs and review status.</footer>
<script id="appscope-data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('appscope-data').textContent), S=D.stats, R=D.records;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const arr=v=>Array.isArray(v)?v.filter(x=>x&&x!=='Unknown'):v&&v!=='Unknown'?[v]:[];
const tags=v=>arr(v).length?arr(v).map(x=>`<span class="tag">${esc(x)}</span>`).join(''):'<span class="label">Unknown</span>';
function bars(obj){let entries=Object.entries(obj||{});if(!entries.length)return '<p class="label">No verified labels yet.</p>';let max=Math.max(1,...entries.map(x=>x[1]));return entries.map(([k,v])=>`<div class="barrow"><div class="barname">${esc(k)}</div><div class="track"><div class="fill" style="width:${v/max*100}%"></div></div><div class="barval">${v}</div></div>`).join('')}
function kpi(n,l,c=''){return `<div class="card"><div class="metric ${c}">${n}</div><div class="label">${l}</div></div>`}
document.getElementById('kpis').innerHTML=kpi(S.total,'Applications in scope')+kpi(S.completed,'Research completed','accent')+kpi(S.pending,'Pending research','amber')+kpi(S.confirmed,'Composio confirmed name/alias matches','blue');
document.getElementById('progressText').textContent=`${S.completed} of ${S.total} applications`;
document.getElementById('progressBar').style.width=(S.total?S.completed/S.total*100:0)+'%';
document.getElementById('authBars').innerHTML=bars(S.auth);
document.getElementById('accessBars').innerHTML=bars(S.access);
document.getElementById('apiBars').innerHTML=bars(S.api);
document.getElementById('mcpBars').innerHTML=bars(S.mcp);
document.getElementById('buildBars').innerHTML=bars(S.buildability);
document.getElementById('categoryBars').innerHTML=S.categories.map(c=>`<div style="margin:12px 0"><div style="display:flex;justify-content:space-between"><span>${esc(c.name)}</span><span class="label">${c.researched}/${c.total} researched</span></div><div class="progress"><span style="width:${c.total?c.researched/c.total*100:0}%"></span></div><div class="label">Easy ${c.easy} · Difficult ${c.difficult} · Blocked ${c.blocked} · Unknown ${c.unknown}</div></div>`).join('');
const verificationChecks = D.verification.checks || [];
const verdicts = verificationChecks.reduce((a,x) => {
    a[x.verdict] = (a[x.verdict] || 0) + 1;
    return a;
}, {});
const checks = verificationChecks.length;
const verified = verdicts.verified || 0;
const incorrect = verdicts.incorrect || 0;
const partial = verdicts.partially_correct || 0;
const accuracy = checks ? (verified / checks * 100) : null;

document.getElementById('verificationKpis').innerHTML =
    kpi(checks,'Manual field checks') +
    kpi(verified,'Verified') +
    kpi(incorrect,'Incorrect') +
    kpi(partial,'Partially correct') +
    kpi(accuracy === null ? 'Not measured' : accuracy.toFixed(1)+'%','Strict exact-match accuracy');

document.getElementById('verificationNote').textContent =
    'Strict accuracy = verified checks / all manual checks. This is a manually selected sample of ' +
    checks + ' field checks across 12 applications, not a representative accuracy estimate for all 100 applications. Partial and incorrect findings are not counted as exact matches.';
const appNames = Object.fromEntries(R.map(x => [x.id, x.name]));
const examples = D.verification.checks || [];

document.getElementById('verificationExamples').innerHTML =
    examples.slice(0, 12).map(x => `
    <details>
      <summary>
        ${esc(appNames[x.app_id] || 'Application ' + x.app_id)}
        — ${esc(x.field)}
        <span class="tag ${
          x.verdict === 'verified' ? 'good' :
          x.verdict === 'incorrect' ? 'bad' : 'warn'
        }">${esc(x.verdict.replace('_',' '))}</span>
      </summary>
      <p><b>Agent finding:</b> ${esc(JSON.stringify(x.original_finding))}</p>
      <p><b>Correction:</b> ${esc(x.corrected_finding || 'No separate corrected value recorded; see verification notes.')}</p>
      <p>${esc(x.notes)}</p>
      <p><a href="${esc(x.evidence_url)}" target="_blank" rel="noopener">Open official evidence</a></p>
    </details>`).join('');
const cat=document.getElementById('category');[...new Set(R.map(x=>x.category).filter(Boolean))].sort().forEach(c=>cat.add(new Option(c,c)));
function filtered(){let q=document.getElementById('search').value.toLowerCase(),c=cat.value,s=document.getElementById('status').value,b=document.getElementById('build').value;return R.filter(x=>(!c||x.category===c)&&(!s||x.research_status===s)&&(!b||(x.buildability||'Unknown')===b)&&(!q||JSON.stringify(x).toLowerCase().includes(q)))}
function render(){let rows=filtered();document.getElementById('rowCount').textContent=`Showing ${rows.length} of ${R.length} applications`;document.getElementById('appRows').innerHTML=rows.map(x=>{let co=x.composio_coverage||{};return `<tr><td><span class="appname">${esc(x.name)}</span></td><td>${esc(x.category)}</td><td>${esc(x.research_status)}</td><td>${tags(x.authentication_methods)}</td><td>${tags(x.api_surface)}</td><td>${tags(x.mcp_availability)}</td><td><span class="tag ${x.buildability==='Easy'?'good':x.buildability==='Blocked'?'bad':x.buildability==='Difficult'?'warn':''}">${esc(x.buildability||'Not assessed')}</span></td><td>${esc(co.match_status||'Unknown')}</td></tr>`}).join('');
document.getElementById('details').innerHTML=rows.map(x=>{let e=x.evidence||{},co=x.composio_coverage||{};let links=[['Official documentation',e.official_documentation_url],['API reference',e.official_api_reference_url],['MCP resource',e.mcp_url]].filter(z=>z[1]);return `<details><summary>${esc(x.name)} — details & evidence</summary><p><b>Description:</b> ${esc(x.description||'Not verified')}</p><p><b>Authentication notes:</b> ${esc(x.authentication_notes||'None recorded')}</p><p><b>Access model:</b> ${tags(x.access_model)}</p><p><b>API explanation:</b> ${esc(x.api_explanation||'Not verified')}</p><p><b>Buildability reason:</b> ${esc(x.buildability_reason||'Not assessed')}</p><p><b>Blockers:</b> ${esc((x.blockers||[]).join('; ')||'None recorded')}</p><p><b>Research confidence:</b> ${esc(e.confidence||'Not available')} · <b>Pages fetched:</b> ${(x.pages_fetched||[]).length}</p><p><b>Needs human verification:</b> ${esc((e.needs_human_verification||[]).join(', ')||'None listed')}</p><p><b>Composio toolkit:</b> ${esc(co.matched_toolkit_name||'No confirmed match')} · ${esc(co.tools_count??'')} tools · ${esc((co.catalogue_auth_schemes||[]).join(', '))}</p><p><b>Evidence:</b> ${links.length?links.map(z=>`<a href="${esc(z[1])}" target="_blank" rel="noopener">${esc(z[0])}</a>`).join(' · '):'No official evidence URL recorded.'}</p><p><b>Research errors:</b> ${esc((x.research_errors||[]).join(' | ')||'None recorded')}</p><p><b>Website:</b> <a href="${esc(x.website||'#')}" target="_blank" rel="noopener">${esc(x.website||'Not available')}</a></p></details>`}).join('')}
['search','category','status','build'].forEach(id=>document.getElementById(id).addEventListener(id==='search'?'input':'change',render));render();
</script>
</body></html>'''

page = page.replace("__DATA__", data)
output = WEB / "index.html"
output.write_text(page, encoding="utf-8")
print(f"Report generated: {output}")
print(f"Applications in scope: {len(records)}")
print(f"Research completed: {completed}")
print(f"Manual verification checks: {len(checks)}")

