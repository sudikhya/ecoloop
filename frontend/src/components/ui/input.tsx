import type { InputHTMLAttributes, Ref } from "react";

export function Input({ className = "", ref, ...props }: InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  return <input ref={ref} className={`min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink placeholder:text-muted/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/15 ${className}`} {...props} />;
}

