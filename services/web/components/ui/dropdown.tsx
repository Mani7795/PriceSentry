"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

interface Option {
  value: string;
  label: string;
}

interface Props {
  label: string;            // button label (e.g. "Brand")
  value?: string;           // currently selected value
  options: Option[];
  onPick: (value: string | undefined) => void;  // undefined = clear
  align?: "left" | "right";
}

// A compact filter dropdown: a pill button that opens an animated popover.
export function Dropdown({ label, value, options, onPick, align = "left" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const active = value != null;
  const selectedLabel = options.find((o) => o.value === value)?.label;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm whitespace-nowrap transition-colors",
          active
            ? "bg-primary text-primary-fg border-primary"
            : "bg-surface border-border text-text hover:border-primary"
        )}
      >
        {active ? selectedLabel : label}
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            className={cn(
              "absolute z-30 mt-1.5 w-56 max-h-72 overflow-y-auto rounded-xl border border-border bg-surface p-1.5 shadow-xl",
              align === "right" ? "right-0" : "left-0"
            )}
          >
            {active && (
              <button
                onClick={() => { onPick(undefined); setOpen(false); }}
                className="w-full text-left rounded-lg px-2.5 py-1.5 text-xs text-muted hover:bg-bg"
              >
                Clear
              </button>
            )}
            {options.map((o) => (
              <button
                key={o.value}
                onClick={() => { onPick(o.value); setOpen(false); }}
                className={cn(
                  "w-full text-left rounded-lg px-2.5 py-1.5 text-sm capitalize hover:bg-bg",
                  value === o.value && "bg-bg font-medium text-primary"
                )}
              >
                {o.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
