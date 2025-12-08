interface SelectOption {
  value: string;
  label: string;
  sublabel?: string;
}

interface SelectProps {
  label: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
}

export default function Select({ label, options, value, onChange }: SelectProps) {
  return (
    <div className="w-full">
      <label className="block text-sm text-gray-400 mb-2">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-dark-elevated border border-dark-border rounded-2xl py-4 px-4 text-white appearance-none focus:outline-none focus:border-accent-cyan transition-colors cursor-pointer"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label} {option.sublabel && `- ${option.sublabel}`}
            </option>
          ))}
        </select>
        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none">
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  );
}
