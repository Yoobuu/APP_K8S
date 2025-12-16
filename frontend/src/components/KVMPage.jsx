export default function KVMPage() {
  return (
    <div className="flex min-h-full items-center justify-center rounded-2xl border border-neutral-200 bg-white p-8 shadow">
      <div className="max-w-xl space-y-3 text-center">
        <h1 className="text-2xl font-semibold text-neutral-900">Inventario KVM</h1>
        <p className="text-neutral-600">
          Estamos preparando la integración con los nodos KVM y Libvirt. Mientras tanto, puedes descargar el inventario
          manual o solicitar acceso al equipo de virtualización.
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <a
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-500"
            href="mailto:ti-inventario@usfq.edu.ec?subject=Inventario%20KVM"
          >
            Solicitar actualización
          </a>
          <button
            type="button"
            className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-semibold text-neutral-700 transition hover:border-neutral-400"
            onClick={() => window.open("https://intranet.usfq.edu.ec/documentos", "_blank", "noopener")}
          >
            Documentación relacionada
          </button>
        </div>
      </div>
    </div>
  )
}
