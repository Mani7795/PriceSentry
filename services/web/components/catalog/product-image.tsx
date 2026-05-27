"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";
import { productGradient } from "@/lib/format";
import { cn } from "@/lib/cn";

interface Props {
  src?: string | null;
  seed: string;          // brand/title for the gradient fallback
  alt: string;
  className?: string;
  rounded?: string;
}

// Renders the real product image; falls back to a deterministic gradient if
// there's no URL or the image fails to load. Plain <img> (not next/image) so
// we don't need remote-domain config in the standalone build.
export function ProductImage({ src, seed, alt, className, rounded = "" }: Props) {
  const [errored, setErrored] = useState(false);
  const showImage = !!src && !errored;

  return (
    <div
      className={cn("relative overflow-hidden bg-white dark:bg-slate-900", rounded, className)}
      style={!showImage ? { background: productGradient(seed) } : undefined}
    >
      {showImage ? (
        <img
          src={src as string}
          alt={alt}
          loading="lazy"
          onError={() => setErrored(true)}
          className="w-full h-full object-contain"
        />
      ) : (
        <div className="w-full h-full grid place-items-center text-white/70">
          <ImageOff className="w-6 h-6" />
        </div>
      )}
    </div>
  );
}
