type BadgeProps = {
  children: string;
  tone?: "black" | "green" | "red" | "amber";
};

export default function Badge({ children, tone = "black" }: BadgeProps) {
  const styles =
    tone === "green"
      ? "bg-emerald-100 text-emerald-700"
      : tone === "red"
      ? "bg-red-100 text-red-700"
      : tone === "amber"
      ? "bg-amber-100 text-amber-700"
      : "bg-black text-white";

  return (
    <span
      className={`inline-flex rounded-full px-5 py-2 text-sm font-black ${styles}`}
    >
      {children}
    </span>
  );
}