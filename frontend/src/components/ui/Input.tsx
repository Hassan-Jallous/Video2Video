interface InputProps {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "url" | "number";
  icon?: React.ReactNode;
}

export default function Input({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  icon,
}: InputProps) {
  return (
    <div className="w-full">
      <label className="block text-sm text-gray-400 mb-2">{label}</label>
      <div className="relative">
        {icon && (
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
            {icon}
          </div>
        )}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full bg-dark-elevated border border-dark-border rounded-2xl py-4 px-4 ${
            icon ? "pl-12" : ""
          } text-white placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors`}
        />
      </div>
    </div>
  );
}
