import { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`border border-[#e8e8e3] bg-white p-8 ${className}`}
    >
      {children}
    </div>
  );
}
