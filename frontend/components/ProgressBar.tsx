import React from "react";
import { motion } from "framer-motion";

interface ProgressBarProps {
  progress: number; // 0 to 100
  className?: string;
  showLabel?: boolean;
}

export default function ProgressBar({
  progress,
  className,
  showLabel = false,
}: ProgressBarProps) {
  // Clamp progress between 0 and 100
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-medium text-foreground">
            {Math.round(clampedProgress)}%
          </span>
        </div>
      )}
      <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-emerald-500 rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${clampedProgress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
