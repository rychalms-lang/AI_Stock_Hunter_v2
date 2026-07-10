import { ReactNode } from "react";

type ButtonProps = {
  children: ReactNode;
  variant?: "primary" | "secondary";
  className?: string;
};

export default function Button({
  children,
  variant = "primary",
  className = "",
}: ButtonProps) {
  const styles =
    variant === "primary"
      ? "bg-black text-white"
      : "border border-neutral-300 bg-transparent text-black";

  return (
    <button
      className={`rounded-full px-7 py-3 text-sm font-bold transition hover:scale-[1.02] ${styles} ${className}`}
    >
      {children}
    </button>
  );
}
