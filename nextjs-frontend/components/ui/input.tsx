import * as React from "react";

import { cn } from "@/lib/utils";
import { X } from "lucide-react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  clearable?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, clearable, value, disabled, onChange, ...props }, ref) => {
    const hasValue =
      clearable === true &&
      value !== undefined &&
      value !== null &&
      String(value).length > 0;

    let innerEl: HTMLInputElement | null = null;
    const setRefs = (el: HTMLInputElement | null) => {
      innerEl = el;
      if (typeof ref === "function") ref(el);
      else if (ref) (ref as React.MutableRefObject<HTMLInputElement | null>).current = el;
    };

    const inputEl = (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          hasValue ? "pr-9" : "",
          className,
        )}
        ref={setRefs}
        value={value}
        disabled={disabled}
        onChange={onChange}
        {...props}
      />
    );

    if (!hasValue) return inputEl;

    return (
      <div className="relative">
        {inputEl}
        <button
          type="button"
          aria-label="입력값 지우기"
          className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          disabled={disabled}
          onClick={() => {
            if (disabled) return;

            // For controlled inputs: make React reliably notice the change.
            // Use the native value setter + dispatch input/change + call onChange directly.
            if (innerEl) {
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype,
                "value",
              )?.set;
              if (setter) setter.call(innerEl, "");
              else innerEl.value = "";

              innerEl.dispatchEvent(new Event("input", { bubbles: true }));
              innerEl.dispatchEvent(new Event("change", { bubbles: true }));
              innerEl.focus();
            }

            onChange?.(
              { target: { value: "" } } as unknown as React.ChangeEvent<HTMLInputElement>,
            );
          }}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  },
);
Input.displayName = "Input";

export { Input };
