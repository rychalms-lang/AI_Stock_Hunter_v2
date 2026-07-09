type SectionHeadingProps = {
  eyebrow: string;
  title?: string;
  description?: string;
};

export default function SectionHeading({
  eyebrow,
  title,
  description,
}: SectionHeadingProps) {
  return (
    <div>
      <div className="text-xs font-black uppercase tracking-[0.25em] text-neutral-500">
        {eyebrow}
      </div>

      {title && (
        <h2 className="mt-5 text-5xl font-black tracking-[-0.08em]">
          {title}
        </h2>
      )}

      {description && (
        <p className="mt-5 max-w-3xl text-base leading-7 text-neutral-600">
          {description}
        </p>
      )}
    </div>
  );
}