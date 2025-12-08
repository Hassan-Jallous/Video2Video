import Link from "next/link";

interface StatRowProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  href?: string;
  color?: "cyan" | "purple" | "orange" | "green";
}

const colorMap = {
  cyan: "text-accent-cyan",
  purple: "text-accent-purple",
  orange: "text-accent-orange",
  green: "text-accent-green",
};

export default function StatRow({ icon, label, value, href, color = "cyan" }: StatRowProps) {
  const content = (
    <div className="flex items-center justify-between py-4 border-b border-dark-border last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-2xl bg-dark-elevated flex items-center justify-center ${colorMap[color]}`}>
          {icon}
        </div>
        <span className="text-gray-300">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-semibold ${colorMap[color]}`}>{value}</span>
        {href && (
          <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        )}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block active:bg-dark-elevated/50 -mx-4 px-4 transition-colors">
        {content}
      </Link>
    );
  }

  return content;
}
