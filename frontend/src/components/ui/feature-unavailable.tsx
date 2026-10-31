import { WrenchIcon } from "@phosphor-icons/react/dist/ssr";

export function FeatureUnavailable({ title, description }: { title: string; description: string }) {
  return (
    <section className="border border-dashed border-line bg-panel p-8 text-center" role="status">
      <WrenchIcon className="mx-auto text-muted" size={30} />
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">{description}</p>
      <span className="mt-5 inline-block bg-canvas px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-muted">Backend capability chưa có</span>
    </section>
  );
}
