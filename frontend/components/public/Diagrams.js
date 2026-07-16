function Box({ x, y, w, h, title, lines = [], tone = "light" }) {
  const fill = tone === "dark" ? "#181b22" : tone === "blue" ? "#eaf2fd" : "#f7f8fa";
  const stroke = tone === "blue" ? "#8fb4ee" : "#cfd4dd";
  const titleFill = tone === "dark" ? "#f1f3f7" : "#17191e";
  const textFill = tone === "dark" ? "#aab0bd" : "#646a75";
  return <g><rect x={x} y={y} width={w} height={h} rx="12" fill={fill} stroke={stroke}/><text x={x+14} y={y+23} fill={titleFill} fontSize="12" fontWeight="600">{title}</text>{lines.map((line,i)=><text key={line} x={x+14} y={y+43+i*16} fill={textFill} fontSize="9.5">{line}</text>)}</g>;
}
function Arrow({ x1,y1,x2,y2,label }) { return <g><path d={`M${x1} ${y1} L${x2} ${y2}`} stroke="#6f7785" strokeWidth="1.3" markerEnd="url(#arrow)"/>{label?<text x={(x1+x2)/2} y={(y1+y2)/2-5} textAnchor="middle" fill="#737a87" fontSize="9">{label}</text>:null}</g>; }
function Frame({ children, label }) { return <div className="overflow-x-auto rounded-[26px] border border-line bg-paper p-4 surface-glow"><div className="mb-3 text-[10px] font-semibold uppercase tracking-[.18em] text-ink-faint">{label}</div>{children}</div>; }

export function InfrastructureDiagram() {
  return <Frame label="Production topology"><svg viewBox="0 0 940 410" className="min-w-[760px] w-full"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6f7785"/></marker></defs>
    <Box x={20} y={155} w={150} h={90} title="Browser" lines={["Next.js product UI","Auth + dashboard","Docs + public site"]} tone="blue"/>
    <Box x={235} y={120} w={175} h={160} title="Application API" lines={["FastAPI","JWT + tenancy","Rate limits","RCA / compliance","Audit + persistence"]} tone="dark"/>
    <Box x={485} y={35} w={180} h={110} title="Agent service" lines={["LangGraph orchestration","Query classification","Evidence composition","Safe result contract"]}/>
    <Box x={485} y={245} w={180} h={110} title="Ingestion workers" lines={["Parsing + OCR","Chunking","Embeddings","Entity extraction"]}/>
    <Box x={745} y={20} w={170} h={82} title="PostgreSQL + pgvector" lines={["Business records","Chunks + embeddings"]} tone="blue"/>
    <Box x={745} y={124} w={170} h={82} title="Neo4j" lines={["Entities + relations","Evidence mappings"]}/>
    <Box x={745} y={228} w={170} h={82} title="Object storage" lines={["Source documents","Versioned artifacts"]}/>
    <Box x={745} y={332} w={170} h={58} title="Redis" lines={["Rate limits + cache"]}/>
    <Arrow x1={170} y1={200} x2={235} y2={200} label="HTTPS"/><Arrow x1={410} y1={160} x2={485} y2={95} label="query"/><Arrow x1={410} y1={240} x2={485} y2={300} label="ingest"/><Arrow x1={665} y1={85} x2={745} y2={62}/><Arrow x1={665} y1={105} x2={745} y2={165}/><Arrow x1={665} y1={285} x2={745} y2={269}/><Arrow x1={410} y1={190} x2={745} y2={365}/>
  </svg></Frame>;
}

export function AgentWorkflowDiagram() {
  const nodes=[[20,"Request scope"],[170,"Classify intent"],[320,"Resolve entities"],[470,"Plan retrieval"],[620,"Retrieve + rerank"],[770,"Compose evidence"]];
  return <Frame label="Agentic query workflow"><svg viewBox="0 0 940 220" className="min-w-[760px] w-full"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6f7785"/></marker></defs>{nodes.map(([x,t],i)=><g key={t}><Box x={x} y={55} w={130} h={78} title={`${i+1}. ${t}`} lines={i===4?["vector","graph","metadata"]:i===5?["claims","citations","gaps"]:[] } tone={i===5?"blue":"light"}/>{i<nodes.length-1?<Arrow x1={x+130} y1={94} x2={nodes[i+1][0]} y2={94}/>:null}</g>)}<path d="M835 145 C835 190, 410 195, 410 140" fill="none" stroke="#8a6d1f" strokeDasharray="5 5" markerEnd="url(#arrow)"/><text x="620" y="188" fill="#8a6d1f" fontSize="9.5">evidence verification can request another bounded retrieval pass</text></svg></Frame>;
}

export function IngestionWorkflowDiagram() {
  return <Frame label="Document ingestion workflow"><svg viewBox="0 0 940 280" className="min-w-[760px] w-full"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6f7785"/></marker></defs>
  {[[20,"Upload session",["MIME + size","site + asset"]],[195,"Parse / OCR",["pages","tables","layout"]],[370,"Chunk",["section-aware","overlap"]],[545,"Enrich",["metadata","entities"]],[720,"Index",["pgvector","Neo4j"]]].map(([x,t,l],i)=><g key={t}><Box x={x} y={55} w={150} h={100} title={t} lines={l} tone={i===4?"blue":"light"}/>{i<4?<Arrow x1={x+150} y1={105} x2={x+175} y2={105}/>:null}</g>)}<Box x={285} y={195} w={370} h={58} title="Provenance envelope" lines={["document → revision → chunk → page / locator → extraction version → review state"]} tone="dark"/><Arrow x1={445} y1={155} x2={445} y2={195}/></svg></Frame>;
}

export function GovernanceWorkflowDiagram() {
  return <Frame label="Governed knowledge lifecycle"><svg viewBox="0 0 940 230" className="min-w-[760px] w-full"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6f7785"/></marker></defs>{[[30,"Draft"],[210,"Submitted"],[390,"Under review"],[570,"Approved"],[750,"Superseded"]].map(([x,t],i)=><g key={t}><Box x={x} y={62} w={140} h={72} title={t} lines={i===2?["role check","evidence check"]:[] } tone={i===3?"blue":"light"}/>{i<4?<Arrow x1={x+140} y1={98} x2={x+180} y2={98}/>:null}</g>)}<path d="M460 142 C460 195, 260 195, 260 142" fill="none" stroke="#9a463a" strokeDasharray="5 5" markerEnd="url(#arrow)"/><text x="360" y="188" fill="#9a463a" fontSize="9.5">reject with reason</text></svg></Frame>;
}
