import { DISCLAIMER } from "../types";

export function Header() {
  return (
    <header className="fixed left-0 top-0 z-50 flex h-16 w-full animate-slide-down-header items-center justify-between border-b border-outline-variant bg-surface/90 px-6 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.5)] backdrop-blur-md">
      <div className="flex items-center gap-4">
        <span className="material-symbols-outlined filled text-[28px] text-primary">
          account_balance
        </span>
        <span className="text-lg font-semibold tracking-tight text-on-surface">
          Kotak Mutual Fund FAQ Assistant
        </span>
      </div>
      <nav className="hidden h-full animate-fade-up-page items-end md:flex">
        <span className="border-b-2 border-primary pb-1 text-sm font-bold text-primary">Dashboard</span>
      </nav>
    </header>
  );
}

export function ComplianceBanner() {
  return (
    <div className="mb-4 w-full max-w-[1200px] animate-slide-down-banner px-6">
      <div className="flex items-center gap-2 rounded-r-lg border-l-4 border-[#F59E0B] bg-[#451a03]/90 px-4 py-2 backdrop-blur-md">
        <span className="material-symbols-outlined filled text-[#F59E0B]">shield</span>
        <span className="text-sm text-on-surface">{DISCLAIMER}</span>
      </div>
    </div>
  );
}
