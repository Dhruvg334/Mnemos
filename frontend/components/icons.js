export function Icon({ name, className = "" }) {
  const common = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, className };
  switch (name) {
    case "overview":
      return (<svg {...common}><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></svg>);
    case "assets":
      return (<svg {...common}><circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" /></svg>);
    case "investigations":
      return (<svg {...common}><circle cx="10" cy="10" r="6.5" /><path d="M15 15l6 6" /><path d="M10 7v3l2 2" /></svg>);
    case "compliance":
      return (<svg {...common}><path d="M9 12l2 2 4-4" /><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /></svg>);
    case "graph":
      return (<svg {...common}><circle cx="6" cy="6" r="2.3" /><circle cx="18" cy="6" r="2.3" /><circle cx="12" cy="18" r="2.3" /><path d="M8 7l6 9M16 7l-6 9M8.3 6h7.4" /></svg>);
    case "documents":
      return (<svg {...common}><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M9 12h6M9 16h6" /></svg>);
    case "expert":
      return (<svg {...common}><path d="M12 3a4 4 0 014 4c0 2.5-2 3.5-2 5.5V14H10v-1.5C10 10.5 8 9.5 8 7a4 4 0 014-4z" /><path d="M9.5 17.5h5M10 20.5h4" /></svg>);
    case "flag":
      return (<svg {...common}><path d="M5 3v18M5 4h11l-2.5 4L16 12H5" /></svg>);
    case "gap":
      return (<svg {...common}><circle cx="12" cy="12" r="9" strokeDasharray="3 3" /><path d="M12 8v5M12 16h.01" /></svg>);
    case "search":
      return (<svg {...common}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>);
    case "bell":
      return (<svg {...common}><path d="M6 8a6 6 0 0112 0c0 4 1.5 5.5 2 6H4c.5-.5 2-2 2-6z" /><path d="M10 20a2 2 0 004 0" /></svg>);
    case "clock":
      return (<svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 8v4l3 2" /></svg>);
    case "close":
      return (<svg {...common}><path d="M6 6l12 12M18 6L6 18" /></svg>);
    case "plant":
      return (<svg {...common}><path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1m4 0h1m-6 4h1m4 0h1m-6 4h1m4 0h1" /></svg>);
    case "shield":
      return (<svg {...common}><path d="M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6z" /></svg>);
    case "query":
      return (<svg {...common}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /><path d="M8 11h6M11 8v6" /></svg>);
    case "agentic":
      return (<svg {...common}><path d="M12 2a4 4 0 014 4c0 2-1.5 3-1.5 5v2h-5v-2C9.5 9 8 8 8 6a4 4 0 014-4z" /><path d="M7 16h10M8.5 19h7M10 22h4" /><circle cx="12" cy="12" r="2" fill="currentColor" /></svg>);
    case "results":
      return (<svg {...common}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 12l3 3 5-5" /></svg>);
    case "org":
      return (<svg {...common}><path d="M3 21h18M5 21V7l7-4 7 4v14" /><path d="M9 9h1m4 0h1m-6 4h6" /></svg>);
    case "users":
      return (<svg {...common}><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" /></svg>);
    case "settings":
      return (<svg {...common}><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>);
    case "chevron":
      return (<svg {...common} viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" /></svg>);
    case "chevron-right":
      return (<svg {...common} viewBox="0 0 16 16"><path d="M6 4l4 4-4 4" /></svg>);
    case "check":
      return (<svg {...common}><path d="M5 13l4 4L19 7" /></svg>);
    case "copy":
      return (<svg {...common}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>);
    case "external":
      return (<svg {...common}><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>);
    case "arrow-up":
      return (<svg {...common}><line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" /></svg>);
    case "layers":
      return (<svg {...common}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>);
    case "cpu":
      return (<svg {...common}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" /></svg>);
    case "db":
      return (<svg {...common}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 5v6c0 1.66-4 3-9 3s-9-1.34-9-3V5" /><path d="M21 11v6c0 1.66-4 3-9 3s-9-1.34-9-3v-6" /></svg>);
    case "brain":
      return (<svg {...common}><path d="M12 3a4 4 0 00-4 4c0 2.5 1.5 3.5 1.5 5.5V15h5v-2.5c0-2 1.5-3 1.5-5.5a4 4 0 00-4-4z" /><path d="M9 17.5h6M9.5 20.5h5" /><path d="M7 7a5 5 0 00-3 2M17 7a5 5 0 013 2" /></svg>);
    case "filter":
      return (<svg {...common}><polygon points="4 3 20 3 13 12 13 20 11 22 11 12 4 3" /></svg>);
    case "logout":
      return (<svg {...common}><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>);
    case "refresh":
      return (<svg {...common}><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" /></svg>);
    case "pulse":
      return (<svg {...common}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>);
    case "archive":
      return (<svg {...common}><polyline points="21 8 21 21 3 21 3 8" /><rect x="1" y="3" width="22" height="5" /><line x1="10" y1="12" x2="14" y2="12" /></svg>);
    case "lock":
      return (<svg {...common}><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg>);
    case "edit":
      return (<svg {...common}><path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5z" /></svg>);
    case "switch":
      return (<svg {...common}><path d="M8 17l-4 4m0 0l4 4m-4-4h16M16 7l4-4m0 0l-4-4m4 4H4" /></svg>);
    case "trash":
      return (<svg {...common}><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" /><path d="M10 11v6M14 11v6M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" /></svg>);
    default:
      return null;
  }
}
