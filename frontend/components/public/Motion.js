export function FadeIn({ children, className = "", delay = 0 }) {
  return (
    <div className={`motion-enter ${className}`} style={{ animationDelay: `${delay}s` }}>
      {children}
    </div>
  );
}

export function FloatCard({ children, className = "", delay = 0 }) {
  return (
    <div className={`motion-enter motion-lift ${className}`} style={{ animationDelay: `${delay}s` }}>
      {children}
    </div>
  );
}
