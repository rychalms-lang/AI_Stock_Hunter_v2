import { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`bg-white p-8 shadow-sm ring-1 ring-neutral-200 ${className}`}
    >
      {children}
    </div>
  );
}