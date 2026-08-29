export function Footer() {
  return (
    <footer className="mt-auto flex w-full flex-col items-center justify-between gap-2 border-t border-outline-variant bg-surface-container-lowest/90 px-6 py-4 backdrop-blur-md md:flex-row lg:pl-[260px]">
      <div className="text-xs font-semibold text-on-surface-variant">
        © 2026 Kotak Mutual Fund. For informational purposes only.
      </div>
      <div className="flex gap-6">
        <a
          href="#"
          className="text-xs font-semibold text-on-surface-variant transition-all hover:text-on-surface hover:underline"
        >
          Privacy Policy
        </a>
        <a
          href="#"
          className="text-xs font-semibold text-on-surface-variant transition-all hover:text-on-surface hover:underline"
        >
          Terms of Use
        </a>
        <a
          href="#"
          className="text-xs font-semibold text-on-surface-variant transition-all hover:text-on-surface hover:underline"
        >
          SEBI Disclosures
        </a>
      </div>
    </footer>
  );
}
