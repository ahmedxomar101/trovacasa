/**
 * Extract gallery image URLs from raw_data JSON.
 * Ported from pipeline/src/report.py lines 98-120.
 */
export function extractGalleryUrls(
  rawData: string | null,
  source: string
): string[] {
  if (!rawData) return [];

  try {
    const rd = JSON.parse(rawData);

    if (source === "idealista") {
      const mm = rd?.multimedia;
      if (mm && typeof mm === "object") {
        const images = mm.images;
        if (Array.isArray(images)) {
          return images
            .filter(
              (img: Record<string, unknown>) =>
                typeof img === "object" && img?.url
            )
            .map((img: Record<string, unknown>) => img.url as string);
        }
      }
    } else if (source === "immobiliare") {
      const media = rd?.media;
      if (media && typeof media === "object") {
        const urls: string[] = [];
        if (Array.isArray(media.images)) {
          for (const img of media.images) {
            if (typeof img === "object") {
              const url = img?.hd || img?.sd;
              if (url) urls.push(url);
            }
          }
        }
        if (Array.isArray(media.floorPlans)) {
          for (const fp of media.floorPlans) {
            if (typeof fp === "object") {
              const url = fp?.hd || fp?.sd;
              if (url) urls.push(url);
            }
          }
        }
        return urls;
      }
    }
  } catch {
    // JSON parse error
  }

  return [];
}
