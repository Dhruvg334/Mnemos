const assets = [
  { id:"ast_p117_n", tag:"P-117", name:"Process Pump", site:"site_north", area:"area_rotating", risk:"high", status:"Operating", parent:null, children:[], evidenceHealth:58, openActions:3 },
  { id:"ast_hx221_n", tag:"HX-221", name:"Heat Exchanger", site:"site_north", area:"area_process", risk:"high", status:"Operating", parent:null, children:[], evidenceHealth:72, openActions:2 },
  { id:"ast_c204_n", tag:"C-204", name:"Compressor", site:"site_north", area:"area_utilities", risk:"medium", status:"Operating", parent:null, children:[], evidenceHealth:81, openActions:1 },
];
const docs = [
  { id:"doc_010", title:"OEM Manual — P-117", type:"oem_manual", date:"2026-06-20", asset:"ast_p117_n", revision:"4", body:"OEM guidance for seal alignment, vibration analysis, lubrication, and maintenance inspection." },
  { id:"doc_011", title:"RCA-P091 — Sludge Pump", type:"rca_report", date:"2026-05-11", asset:"ast_p117_n", revision:"2", body:"Prior investigation identifying foundation looseness and coupling misalignment." },
  { id:"doc_012", title:"Expert Note — ETP Vibration", type:"expert_note", date:"2026-06-28", asset:"ast_p117_n", revision:"1", body:"Field observation pending engineering validation." },
];
const failures = [
  { id:"fail_1", asset:"ast_p117_n", date:"2026-01-14", severity:"high", summary:"Mechanical seal leakage", workOrder:"wo_1" },
  { id:"fail_2", asset:"ast_p117_n", date:"2026-06-18", severity:"high", summary:"Recurring seal leakage with elevated vibration", workOrder:"wo_2" },
];
const workOrders = [
  { id:"wo_1", no:"WO-2026-0114", asset:"ast_p117_n", status:"Closed" },
  { id:"wo_2", no:"WO-2026-0618", asset:"ast_p117_n", status:"Open" },
];
const requirements = [
  { id:"req_1", code:"SOP-MECH-017", title:"Pump alignment and seal inspection", asset:"ast_p117_n", status:"Expired", validity:"2026-05-31", evidenceFound:2, openActions:1 },
  { id:"req_2", code:"ISO-14224", title:"Failure coding completeness", asset:"ast_p117_n", status:"Complete", validity:"2027-01-01", evidenceFound:3, openActions:0 },
];
const rca = {
  timeline:[
    { date:"2026-01-14", type:"failure", label:"First seal leak recorded", doc:"doc_011" },
    { date:"2026-06-18", type:"failure", label:"Recurring leak with high vibration", doc:"doc_010" },
  ],
  hypotheses:[
    { id:"hyp_1", statement:"Coupling misalignment and overdue lubrication contributed to seal degradation.", status:"unresolved", confidence:76, supporting:["doc_010","doc_011"], opposing:[] },
  ],
  missingEvidence:["Current vibration spectrum", "Post-maintenance laser alignment report"],
  recommendedActions:["Capture vibration spectrum", "Verify alignment and foundation bolts"],
  contradictions:[], claims:[], graphPath:[]
};
const graph = { nodes:[{id:"ast_p117_n",label:"P-117",type:"asset",x:250,y:140}], edges:[] };
const expertKnowledge = [
  { id:"exp_1", title:"Foundation bolt check before re-seal", condition:"Recurring seal leak", rec:"Verify soft foot and foundation torque before replacement.", expert:"Senior technician", date:"2026-06-29", support:"doc_012", status:"Pending" },
];
const copilotAnswer = {
  question:"What is the most likely cause?",
  summary:"Evidence points to recurring misalignment and lubrication gaps, but vibration spectrum evidence is still missing.",
  confidence:74,
  supporting:["doc_010","doc_011"],
  missingEvidence:["Vibration spectrum"],
  relatedAssets:["ast_hx221_n"]
};
export const D = {
  sites:[{id:"site_north",name:"North Process Plant"},{id:"site_south",name:"South Utilities Plant"}],
  areas:[{id:"area_rotating",name:"Rotating Equipment",site:"site_north"},{id:"area_process",name:"Process",site:"site_north"},{id:"area_utilities",name:"Utilities",site:"site_north"}],
  assets, docs, failures, workOrders, requirements, rca, graph, expertKnowledge, copilotAnswer
};
