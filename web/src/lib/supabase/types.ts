// Generated types for Supabase schema
// Regenerate with: npx supabase gen types typescript --project-id [ref] > src/lib/supabase/types.ts

export interface Listing {
  id: string;
  source: string;
  url: string;
  title: string | null;
  address: string | null;
  price: number | null;
  rooms: number | null;
  size_sqm: number | null;
  floor: string | null;
  description: string | null;
  image_url: string | null;
  lat: number | null;
  lon: number | null;
  metro_score: number | null;
  nearest_station: string | null;
  agent: string | null;
  published_date: string | null;
  scraped_at: string | null;
  seen_count: number;
  bathrooms: number | null;
  property_type: string | null;
  elevator: boolean | null;
  balcony: boolean | null;
  terrace: boolean | null;
  energy_class: string | null;
  num_photos: number | null;
  has_video: boolean | null;
  has_3d_tour: boolean | null;
  creation_date: string | null;
  last_modified: string | null;
  price_per_sqm: number | null;
  condo_fees: number | null;
  condo_included: boolean | null;
  available_from: string | null;
  furnished: string | null;
  contract_type: string | null;
  deposit_months: number | null;
  deposit_amount: number | null;
  heating: string | null;
  condition: string | null;
  building_age: string | null;
  agency_fee: string | null;
  red_flags: string | null;
  additional_costs: string | null;
  heating_fuel: string | null;
  air_conditioning: boolean | null;
  orientation: string | null;
  is_private: boolean | null;
  commute_score: number | null;
  quality_score: number | null;
  scam_score: number | null;
  livability_score: number | null;
  freshness_score: number | null;
  neighborhood_score: number | null;
  neighborhood_name: string | null;
  hybrid_score: number | null;
  total_monthly_cost: number | null;
  budget_status: string | null;
  commute_minutes: number | null;
  raw_data: string | null;
  status: string;
  favorited_at: string | null;
  dismissed_at: string | null;
  notified_at: string | null;
  status_updated_at: string | null;
  notes: string | null;
  phone: string | null;
  is_last_floor: boolean | null;
}

export interface PipelineRun {
  id: string;
  started_at: string;
  completed_at: string | null;
  stage: string;
  status: string;
  stats: Record<string, unknown> | null;
  error_message: string | null;
}

// Columns to SELECT in list queries (excludes raw_data which is large)
export const LISTING_LIST_COLUMNS =
  "id, source, url, title, address, price, rooms, size_sqm, floor, image_url, lat, lon, metro_score, nearest_station, agent, hybrid_score, commute_score, commute_minutes, livability_score, quality_score, scam_score, freshness_score, neighborhood_score, neighborhood_name, budget_status, total_monthly_cost, condo_fees, condo_included, furnished, is_private, status, creation_date, scraped_at, energy_class, condition, num_photos, published_date";
