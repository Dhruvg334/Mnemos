export function Icon({ name, className = "" }) {
  const common = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, className };
  switch (name) {
    case "overview":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      );
    case "assets":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" />
        </svg>
      );
    case "investigations":
      return (
        <svg {...common}>
          <circle cx="10" cy="10" r="6.5" />
          <path d="M15 15l6 6" />
          <path d="M10 7v3l2 2" />
        </svg>
      );
    case "compliance":
      return (
        <svg {...common}>
          <path d="M9 12l2 2 4-4" />
          <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
        </svg>
      );
    case "graph":
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="2.3" />
          <circle cx="18" cy="6" r="2.3" />
          <circle cx="12" cy="18" r="2.3" />
          <path d="M8 7l6 9M16 7l-6 9M8.3 6h7.4" />
        </svg>
      );
    case "documents":
      return (
        <svg {...common}>
          <path d="M7 3h7l5 5v13H7z" />
          <path d="M14 3v5h5M9 12h6M9 16h6" />
        </svg>
      );
    case "expert":
      return (
        <svg {...common}>
          <path d="M12 3a4 4 0 014 4c0 2.5-2 3.5-2 5.5V14H10v-1.5C10 10.5 8 9.5 8 7a4 4 0 014-4z" />
          <path d="M9.5 17.5h5M10 20.5h4" />
        </svg>
      );
    case "flag":
      return (
        <svg {...common}>
          <path d="M5 3v18M5 4h11l-2.5 4L16 12H5" />
        </svg>
      );
    case "gap":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" strokeDasharray="3 3" />
          <path d="M12 8v5M12 16h.01" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
      );
    case "bell":
      return (
        <svg {...common}>
          <path d="M6 8a6 6 0 0112 0c0 4 1.5 5.5 2 6H4c.5-.5 2-2 2-6z" />
          <path d="M10 20a2 2 0 004 0" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v4l3 2" />
        </svg>
      );
    case "close":
      return (
        <svg {...common}>
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    case "plant":
      return (
        <svg {...common}>
          <path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1m4 0h1m-6 4h1m4 0h1m-6 4h1m4 0h1" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6z" />
        </svg>
      );
    default:
      return null;
  }
}
