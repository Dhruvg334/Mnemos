const assets = [
  { id:"ast_p117_n", tag:"P-117", name:"Process Pump", type:"pump", site:"site_north", area:"area_rotating", risk:"high", status:"Operating", parent:null, children:[], evidenceHealth:58, openActions:3 },
  { id:"ast_hx221_n", tag:"HX-221", name:"Heat Exchanger", type:"heat_exchanger", site:"site_north", area:"area_process", risk:"high", status:"Operating", parent:null, children:[], evidenceHealth:72, openActions:2 },
  { id:"ast_c204_n", tag:"C-204", name:"Compressor", type:"compressor", site:"site_north", area:"area_utilities", risk:"medium", status:"Operating", parent:null, children:[], evidenceHealth:81, openActions:1 },
  { id:"ast_tk401_n", tag:"TK-401", name:"Storage Tank", type:"tank", site:"site_north", area:"area_rotating", risk:"low", status:"Standby", parent:null, children:[], evidenceHealth:92, openActions:0 },
  { id:"ast_v301_s", tag:"V-301", name:"Pressure Vessel", type:"vessel", site:"site_south", area:"area_process", risk:"medium", status:"Operating", parent:null, children:[], evidenceHealth:76, openActions:1 },
  { id:"ast_m101_s", tag:"M-101", name:"Centrifugal Mixer", type:"mixer", site:"site_south", area:"area_utilities", risk:"low", status:"Operating", parent:null, children:[], evidenceHealth:88, openActions:0 },
];
const docs = [
  { id:"doc_010", title:"OEM Manual — P-117", type:"oem_manual", date:"2026-06-20", asset:"ast_p117_n", revision:"4", body:"OEM guidance for seal alignment, vibration analysis, lubrication, and maintenance inspection.", size_kb: 240 },
  { id:"doc_011", title:"RCA-P091 — Sludge Pump", type:"rca_report", date:"2026-05-11", asset:"ast_p117_n", revision:"2", body:"Prior investigation identifying foundation looseness and coupling misalignment.", size_kb: 180 },
  { id:"doc_012", title:"Expert Note — ETP Vibration", type:"expert_note", date:"2026-06-28", asset:"ast_p117_n", revision:"1", body:"Field observation pending engineering validation.", size_kb: 64 },
  { id:"doc_013", title:"SOP-MECH-017 — Pump Alignment", type:"procedure", date:"2026-03-15", asset:"ast_p117_n", revision:"3", body:"Standard operating procedure for pump alignment and seal inspection.", size_kb: 92 },
  { id:"doc_014", title:"Inspection Report — HX-221", type:"inspection", date:"2026-07-01", asset:"ast_hx221_n", revision:"1", body:"Annual heat exchanger tube inspection. Minor fouling observed in lower bank.", size_kb: 156 },
  { id:"doc_015", title:"ISO 14224 Compliance Guide", type:"standard", date:"2026-01-10", asset:"ast_p117_n", revision:"2", body:"Failure coding completeness requirements per ISO 14224.", size_kb: 210 },
];
const failures = [
  { id:"fail_1", asset:"ast_p117_n", date:"2026-01-14", severity:"high", summary:"Mechanical seal leakage", code:"mechanical_seal_leakage", workOrder:"wo_1" },
  { id:"fail_2", asset:"ast_p117_n", date:"2026-06-18", severity:"high", summary:"Recurring seal leakage with elevated vibration", code:"recurring_seal_leakage", workOrder:"wo_2" },
  { id:"fail_3", asset:"ast_hx221_n", date:"2026-04-22", severity:"medium", summary:"Reduced heat transfer efficiency", code:"reduced_efficiency", workOrder:"wo_3" },
  { id:"fail_4", asset:"ast_c204_n", date:"2026-05-30", severity:"medium", summary:"Abnormal discharge pressure", code:"abnormal_pressure", workOrder:"wo_4" },
];
const workOrders = [
  { id:"wo_1", no:"WO-2026-0114", asset:"ast_p117_n", status:"Closed" },
  { id:"wo_2", no:"WO-2026-0618", asset:"ast_p117_n", status:"Open" },
  { id:"wo_3", no:"WO-2026-0422", asset:"ast_hx221_n", status:"In Progress" },
  { id:"wo_4", no:"WO-2026-0530", asset:"ast_c204_n", status:"Scheduled" },
];
const requirements = [
  { id:"req_1", code:"SOP-MECH-017", title:"Pump alignment and seal inspection", asset:"ast_p117_n", status:"Expired", validity:"2026-05-31", evidenceFound:2, openActions:1 },
  { id:"req_2", code:"ISO-14224", title:"Failure coding completeness", asset:"ast_p117_n", status:"Complete", validity:"2027-01-01", evidenceFound:3, openActions:0 },
  { id:"req_3", code:"API-610", title:"Centrifugal pump design audit", asset:"ast_p117_n", status:"Missing", validity:"2026-08-01", evidenceFound:0, openActions:1 },
  { id:"req_4", code:"ASME-VIII", title:"Pressure vessel integrity", asset:"ast_v301_s", status:"Complete", validity:"2027-06-01", evidenceFound:2, openActions:0 },
];
const rca = {
  timeline:[
    { date:"2026-01-14", type:"failure", label:"First seal leak recorded", doc:"doc_011" },
    { date:"2026-06-18", type:"failure", label:"Recurring leak with high vibration", doc:"doc_010" },
    { date:"2026-06-20", type:"work_order", label:"Work order WO-2026-0618 issued", doc:"doc_010" },
    { date:"2026-06-28", type:"inspection", label:"Expert field inspection completed", doc:"doc_012" },
  ],
  hypotheses:[
    { id:"hyp_1", statement:"Coupling misalignment and overdue lubrication contributed to seal degradation.", status:"unresolved", confidence:76, supporting:["doc_010","doc_011"], opposing:[] },
    { id:"hyp_2", statement:"Foundation bolt loosening due to repetitive thermal cycling.", status:"unresolved", confidence:62, supporting:["doc_011"], opposing:["doc_010"] },
  ],
  missingEvidence:["Current vibration spectrum", "Post-maintenance laser alignment report"],
  recommendedActions:["Capture vibration spectrum", "Verify alignment and foundation bolts"],
  contradictions:[], claims:[], graphPath:[]
};
const graph = {
  nodes:[
    { id:"P-117", label:"P-117", kind:"asset" },
    { id:"M-117", label:"M-117", kind:"asset" },
    { id:"SEAL", label:"Seal leak", kind:"failure" },
    { id:"COUP", label:"Misalignment", kind:"finding" },
    { id:"VIB", label:"Vibration", kind:"finding" },
    { id:"LUBE", label:"Lube gap", kind:"finding" },
    { id:"SOP22", label:"SOP-MECH-017", kind:"procedure" },
    { id:"OEM", label:"OEM Manual", kind:"document" },
    { id:"P091", label:"RCA-P091", kind:"document" },
    { id:"EXPERT", label:"Expert note", kind:"knowledge" },
  ],
  edges:[
    { from:"P-117", to:"SEAL", verified:true },
    { from:"P-117", to:"COUP", verified:true },
    { from:"P-117", to:"VIB", verified:true },
    { from:"M-117", to:"P-117", verified:true },
    { from:"SEAL", to:"LUBE", verified:false },
    { from:"COUP", to:"LUBE", verified:false },
    { from:"VIB", to:"COUP", verified:false },
    { from:"SOP22", to:"P-117", verified:true },
    { from:"OEM", to:"P-117", verified:true },
    { from:"OEM", to:"SEAL", verified:true },
    { from:"P091", to:"P-117", verified:true },
    { from:"P091", to:"SEAL", verified:true },
    { from:"EXPERT", to:"P-117", verified:false },
    { from:"EXPERT", to:"VIB", verified:false },
  ],
};
const expertKnowledge = [
  { id:"exp_1", title:"Foundation bolt check before re-seal", condition:"Recurring seal leak", rec:"Verify soft foot and foundation torque before replacement.", expert:"Senior technician", date:"2026-06-29", support:"doc_012", status:"Pending" },
  { id:"exp_2", title:"Vibration analysis frequency", condition:"New pump installation", rec:"Baseline vibration survey within 72 hours of commissioning.", expert:"Reliability engineer", date:"2026-05-15", support:"doc_010", status:"Approved" },
];
const queries = [
  { id:"q_1", question:"What is the root cause of recurring seal failure on P-117?", status:"completed", timestamp:"2026-07-19T10:30:00Z", latency_ms:3400 },
  { id:"q_2", question:"Show me all compliance gaps for rotating equipment", status:"completed", timestamp:"2026-07-19T09:15:00Z", latency_ms:2100 },
  { id:"q_3", question:"Compare failure rates between North and South plants", status:"completed", timestamp:"2026-07-18T16:45:00Z", latency_ms:5100 },
  { id:"q_4", question:"What expert knowledge exists for heat exchanger fouling?", status:"completed", timestamp:"2026-07-18T14:20:00Z", latency_ms:1800 },
  { id:"q_5", question:"Generate compliance report for P-117", status:"processing", timestamp:"2026-07-19T11:05:00Z", latency_ms:null },
];
const queryResults = {
  q_1: {
    summary: "The recurring seal failure on P-117 is most likely caused by a combination of coupling misalignment and inadequate lubrication maintenance. Vibration analysis data is still missing for definitive confirmation.",
    confidence: 74,
    stages: [
      { name:"Query Understanding", status:"complete", duration_ms:320, detail:"Classified as RCA query for asset P-117" },
      { name:"Retrieval", status:"complete", duration_ms:1100, detail:"Retrieved 4 documents, 2 failures, 1 work order" },
      { name:"Evidence Analysis", status:"complete", duration_ms:890, detail:"Identified 2 supporting, 1 contradicting evidence" },
      { name:"Reasoning", status:"complete", duration_ms:650, detail:"Formulated 2 hypotheses, confidence 76% and 62%" },
      { name:"Compliance Check", status:"complete", duration_ms:340, detail:"1 expired requirement (SOP-MECH-017) flagged" },
    ],
    evidence: [
      { docId:"doc_010", relevance:0.94, snippet:"Seal alignment must be verified during each maintenance cycle per OEM specifications." },
      { docId:"doc_011", relevance:0.87, snippet:"Prior investigation identified foundation looseness as contributing factor." },
      { docId:"doc_012", relevance:0.72, snippet:"Field observation notes elevated vibration on drive end bearing." },
    ],
    missingEvidence:["Current vibration spectrum", "Post-maintenance laser alignment report"],
    relatedAssets:["ast_hx221_n"],
    citations:["doc_010","doc_011","doc_012"],
  },
  q_2: {
    summary: "Found 2 compliance gaps across rotating equipment: SOP-MECH-017 has expired and API-610 audit is missing. 3 requirements are in complete status.",
    confidence: 82,
    stages: [
      { name:"Query Understanding", status:"complete", duration_ms:280, detail:"Classified as compliance query for rotating equipment" },
      { name:"Retrieval", status:"complete", duration_ms:950, detail:"Retrieved 4 requirements, 2 assets" },
      { name:"Evidence Analysis", status:"complete", duration_ms:620, detail:"Analyzed compliance status per requirement" },
      { name:"Reasoning", status:"complete", duration_ms:410, detail:"Prioritized gaps by risk severity" },
      { name:"Compliance Check", status:"complete", duration_ms:290, detail:"2 gaps found, 1 corrective action in progress" },
    ],
    evidence: [
      { docId:"req_1", relevance:0.96, snippet:"SOP-MECH-017 expired on 2026-05-31. Open actions: 1." },
      { docId:"req_3", relevance:0.91, snippet:"API-610 audit is missing. No evidence found." },
      { docId:"req_2", relevance:0.78, snippet:"ISO-14224 compliance is complete with 3 evidence items." },
    ],
    missingEvidence:["API-610 audit report"],
    relatedAssets:["ast_p117_n","ast_hx221_n"],
    citations:["req_1","req_3","req_2"],
  },
};
const organisation = {
  id:"org_1",
  name:"North Process Industries",
  slug:"npi",
  plan:"Enterprise",
  created:"2025-01-15",
  assets:6,
  members:8,
  storage_gb:2.4,
  sites:["North Process Plant","South Utilities Plant"],
};
const members = [
  { id:"usr_1", name:"Alex Chen", email:"alex@npi-industries.com", role:"Admin", status:"Active", joined:"2025-01-15", lastActive:"2026-07-19" },
  { id:"usr_2", name:"Sarah Park", email:"sarah@npi-industries.com", role:"Editor", status:"Active", joined:"2025-02-01", lastActive:"2026-07-18" },
  { id:"usr_3", name:"James Rivera", email:"james@npi-industries.com", role:"Viewer", status:"Active", joined:"2025-03-10", lastActive:"2026-07-17" },
  { id:"usr_4", name:"Maria Santos", email:"maria@npi-industries.com", role:"Editor", status:"Pending", joined:"2026-06-20", lastActive:null },
  { id:"usr_5", name:"Tom Baker", email:"tom@npi-industries.com", role:"Admin", status:"Active", joined:"2025-01-20", lastActive:"2026-07-19" },
  { id:"usr_6", name:"Priya Patel", email:"priya@npi-industries.com", role:"Viewer", status:"Inactive", joined:"2025-04-05", lastActive:"2026-06-01" },
];
const copilotAnswer = {
  question:"What is the most likely cause?",
  summary:"Evidence points to recurring misalignment and lubrication gaps, but vibration spectrum evidence is still missing.",
  confidence:74,
  supporting:["doc_010","doc_011"],
  missingEvidence:["Vibration spectrum"],
  relatedAssets:["ast_hx221_n"],
  claims:[], contradictions:[], graphPath:[], recommendedActions:[], statusLabel:""
};
export const D = {
  sites:[{ id:"site_north", name:"North Process Plant" },{ id:"site_south", name:"South Utilities Plant" }],
  areas:[{ id:"area_rotating", name:"Rotating Equipment", site:"site_north" },{ id:"area_process", name:"Process", site:"site_north" },{ id:"area_utilities", name:"Utilities", site:"site_north" }],
  assets, docs, failures, workOrders, requirements, rca, graph, expertKnowledge,
  queries, queryResults, copilotAnswer,
  organisation, members,
};
