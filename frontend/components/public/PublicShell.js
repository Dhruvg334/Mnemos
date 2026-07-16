import PublicHeader from "./PublicHeader";
import PublicFooter from "./PublicFooter";

export default function PublicShell({ children }) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <PublicHeader />
      <main>{children}</main>
      <PublicFooter />
    </div>
  );
}
