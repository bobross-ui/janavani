import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Janavani Dashboard",
  description: "Civic grievance intelligence dashboard for clustered public issues.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="page">
          <header className="header">
            <div>
              <p className="eyebrow">Janavani</p>
              <h1>Civic issue intelligence</h1>
              <p className="muted">
                Voice-first grievances become structured, redacted, joinable public signals.
              </p>
            </div>
            <nav className="nav" aria-label="Main navigation">
              <Link href="/">Public dashboard</Link>
              <Link href="/admin">Admin workflow</Link>
              <Link href="/evals">Eval reports</Link>
            </nav>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
