"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type ToggleGroupContextValue = {
  value: string | undefined;
  onValueChange?: (value: string) => void;
};

const ToggleGroupContext = React.createContext<ToggleGroupContextValue | null>(
  null
);

export interface ToggleGroupProps
  extends React.HTMLAttributes<HTMLDivElement> {
  type?: "single";
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
}

export function ToggleGroup({
  className,
  value,
  onValueChange,
  disabled,
  ...props
}: ToggleGroupProps) {
  return (
    <ToggleGroupContext.Provider
      value={{
        value,
        onValueChange: disabled ? undefined : onValueChange,
      }}
    >
      <div
        role="group"
        aria-disabled={disabled || undefined}
        className={cn(
          "inline-flex items-center gap-1 rounded-md border bg-background p-1",
          className
        )}
        {...props}
      />
    </ToggleGroupContext.Provider>
  );
}

export interface ToggleGroupItemProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function ToggleGroupItem({
  className,
  value,
  disabled,
  children,
  ...props
}: ToggleGroupItemProps) {
  const ctx = React.useContext(ToggleGroupContext);
  const selected = ctx?.value === value;

  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={() => ctx?.onValueChange?.(value)}
      className={cn(
        "inline-flex h-8 items-center justify-center rounded-sm px-3 text-sm font-medium transition-colors",
        "text-muted-foreground hover:text-foreground",
        selected && "bg-indigo-100 text-foreground shadow-sm",
        disabled && "opacity-50 pointer-events-none",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

