interface CardProps {
  children: React.ReactNode;
  className?: string;
  gradient?: boolean;
  onClick?: () => void;
}

export default function Card({ children, className = "", gradient = false, onClick }: CardProps) {
  const baseClasses = "rounded-3xl p-4 transition-all";
  const bgClasses = gradient
    ? "bg-gradient-card"
    : "bg-dark-card border border-dark-border";
  const interactiveClasses = onClick ? "active:scale-[0.98] cursor-pointer" : "";

  return (
    <div
      className={`${baseClasses} ${bgClasses} ${interactiveClasses} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
