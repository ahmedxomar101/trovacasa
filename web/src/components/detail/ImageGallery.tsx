"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

interface ImageGalleryProps {
  images: string[];
}

export function ImageGallery({ images }: ImageGalleryProps) {
  const [current, setCurrent] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);

  if (images.length === 0) return null;

  const prev = () => setCurrent((c) => (c - 1 + images.length) % images.length);
  const next = () => setCurrent((c) => (c + 1) % images.length);

  return (
    <>
      <div className="relative rounded-xl overflow-hidden bg-zinc-900">
        <img
          src={images[current]}
          alt={`Photo ${current + 1}`}
          className="w-full h-[280px] sm:h-[400px] object-contain bg-black cursor-pointer"
          onClick={() => setFullscreen(true)}
          onError={(e) => {
            (e.target as HTMLImageElement).src = "";
            (e.target as HTMLImageElement).alt = "Image unavailable";
          }}
        />

        {images.length > 1 && (
          <>
            <button
              onClick={prev}
              aria-label="Previous image"
              className="absolute left-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-white active:bg-black/80 touch-manipulation"
            >
              <ChevronLeft size={22} />
            </button>
            <button
              onClick={next}
              aria-label="Next image"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-white active:bg-black/80 touch-manipulation"
            >
              <ChevronRight size={22} />
            </button>
            <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur text-white text-xs font-semibold px-2.5 py-1 rounded-full">
              {current + 1} / {images.length}
            </div>
          </>
        )}
      </div>

      {/* Fullscreen viewer */}
      {fullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/95 backdrop-blur flex items-center justify-center touch-manipulation"
          onClick={() => setFullscreen(false)}
        >
          <button
            onClick={() => setFullscreen(false)}
            aria-label="Close"
            className="absolute top-4 right-4 w-12 h-12 rounded-full bg-white/10 active:bg-white/25 flex items-center justify-center text-white z-10"
          >
            <X size={24} />
          </button>
          {images.length > 1 && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); prev(); }}
                aria-label="Previous"
                className="absolute left-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 active:bg-white/20 flex items-center justify-center text-white"
              >
                <ChevronLeft size={28} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); next(); }}
                aria-label="Next"
                className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 active:bg-white/20 flex items-center justify-center text-white"
              >
                <ChevronRight size={28} />
              </button>
            </>
          )}
          <img
            src={images[current]}
            alt={`Photo ${current + 1}`}
            className="max-w-[95vw] max-h-[85vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {images.length > 1 && (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-black/60 text-white text-sm px-4 py-2 rounded-full">
              {current + 1} / {images.length}
            </div>
          )}
        </div>
      )}
    </>
  );
}
