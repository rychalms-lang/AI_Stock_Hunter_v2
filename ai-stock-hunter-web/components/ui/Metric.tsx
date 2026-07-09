type MetricProps = {
  label: string;
  value: string;
  className?: string;
};

export default function Metric({ label, value, className = "" }: MetricProps) {
  return (
    <div className={`p-6 ${className}`}>
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="mt-3 text-3xl font-black tracking-[-0.06em]">
        {value}
      </div>
    </div>
  );
}