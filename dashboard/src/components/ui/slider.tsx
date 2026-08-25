import * as React from "react";
import { cn } from "@/lib/utils";

interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  value: number;
  min: number;
  max: number;
  onValueChange: (v: number) => void;
}

function Slider({ value, min, max, onValueChange, className, ...props }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="relative w-full">
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-line overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-emergency to-warn transition-[width] duration-100"
          style={{ width: `${pct}%` }}
        />
      </div>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onValueChange(Number(e.target.value))}
        className={cn(
          "relative w-full appearance-none bg-transparent cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(255,255,255,0.6)]",
          className
        )}
        {...props}
      />
    </div>
  );
}

export { Slider };
