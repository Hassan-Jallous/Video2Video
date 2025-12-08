interface ProgressBarProps {
  progress: number; // 0-100
  label?: string;
  showPercentage?: boolean;
}

export default function ProgressBar({ progress, label, showPercentage = true }: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className="w-full">
      {(label || showPercentage) && (
        <div className="flex justify-between items-center mb-2">
          {label && <span className="text-sm text-gray-400">{label}</span>}
          {showPercentage && (
            <span className="text-sm font-semibold text-accent-cyan">
              {clampedProgress.toFixed(1)}%
            </span>
          )}
        </div>
      )}
      <div className="h-2 bg-dark-elevated rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-progress rounded-full transition-all duration-300"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  );
}
