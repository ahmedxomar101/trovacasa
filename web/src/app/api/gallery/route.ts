import { createServerClient } from "@/lib/supabase/server";
import { extractGalleryUrls } from "@/lib/utils/gallery";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get("id");
  if (!id) {
    return NextResponse.json({ urls: [] });
  }

  const supabase = await createServerClient();
  const { data } = await supabase
    .from("listings")
    .select("raw_data, source, image_url")
    .eq("id", id)
    .single();

  if (!data) {
    return NextResponse.json({ urls: [] });
  }

  const urls = extractGalleryUrls(data.raw_data, data.source);

  // If gallery extraction returned nothing, fall back to image_url
  if (urls.length === 0 && data.image_url) {
    return NextResponse.json({ urls: [data.image_url] });
  }

  return NextResponse.json({ urls });
}
