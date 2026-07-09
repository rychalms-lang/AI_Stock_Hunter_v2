import { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`border border-white/10 bg-[#101216] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.28)] ${className}`}
    >
      {children}
    </div>
  );
}
