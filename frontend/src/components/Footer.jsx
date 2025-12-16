export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-neutral-900/80 text-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 text-xs sm:flex-row sm:items-center sm:justify-between sm:text-sm">
        <div>
          <span className="font-semibold">Inventario DC</span> · Universidad San Francisco de Quito
        </div>
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4">
          <span>Versión beta · {new Date().getFullYear()}</span>
          <a
            className="text-emerald-300 transition hover:text-emerald-200"
            href="mailto:ti-inventario@usfq.edu.ec"
          >
            Soporte: ti-inventario@usfq.edu.ec
          </a>
        </div>
      </div>
    </footer>
  );
}
