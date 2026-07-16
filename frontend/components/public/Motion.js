export function FadeIn({ children, className = "", delay = 0 }) {
  return (
    <div
      className={`motion-fade-up ${className}`}
      style={{ animationDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}

export function FloatCard({ children, className = "", delay = 0 }) {
  return (
    <div
      className={`motion-fade-up motion-float-card ${className}`}
      style={{ animationDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}
