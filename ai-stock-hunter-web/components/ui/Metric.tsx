type MetricProps = {
  label: string;
  value: string;
  className?: string;
};

export default function Metric({ label, value, className = "" }: MetricProps) {
  return (
    <div className={`p-6 ${className}`}>
      <div className="text-[11px] font-black uppercase tracking-[0.2em] text-black/42">
        {label}
      </div>
      <div className="mt-3 text-3xl font-black tracking-[-0.06em] text-black">
        {value}
      </div>
    </div>
  );
}
