-- Milan Apartment Finder — Initial Supabase Schema
-- Migrated from SQLite (pipeline/src/db.py)

CREATE TABLE IF NOT EXISTS listings (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL,
    url                 TEXT UNIQUE NOT NULL,
    title               TEXT,
    address             TEXT,
    price               INTEGER,
    rooms               INTEGER,
    size_sqm            INTEGER,
    floor               TEXT,
    description         TEXT,
    image_url           TEXT,
    lat                 DOUBLE PRECISION,
    lon                 DOUBLE PRECISION,
    metro_score         INTEGER,
    nearest_station     TEXT,
    agent               TEXT,
    published_date      TEXT,
    scraped_at          TEXT,
    seen_count          INTEGER DEFAULT 1,

    -- Property details
    bathrooms           INTEGER,
    property_type       TEXT,
    elevator            BOOLEAN,
    balcony             BOOLEAN,
    terrace             BOOLEAN,
    energy_class        TEXT,
    num_photos          INTEGER,
    has_video           BOOLEAN,
    has_3d_tour         BOOLEAN,
    creation_date       TEXT,
    last_modified       TEXT,
    price_per_sqm       DOUBLE PRECISION,

    -- LLM-extracted fields
    condo_fees          DOUBLE PRECISION,
    condo_included      BOOLEAN,
    available_from      TEXT,
    furnished           TEXT,
    contract_type       TEXT,
    deposit_months      INTEGER,
    deposit_amount      DOUBLE PRECISION,
    heating             TEXT,
    condition           TEXT,
    building_age        TEXT,
    agency_fee          TEXT,
    red_flags           TEXT,
    additional_costs    TEXT,
    heating_fuel        TEXT,
    air_conditioning    BOOLEAN,
    orientation         TEXT,
    is_private          BOOLEAN,

    -- Scores
    commute_score       INTEGER,
    quality_score       INTEGER,
    scam_score          INTEGER,
    livability_score    INTEGER,
    freshness_score     INTEGER,
    neighborhood_score  INTEGER,
    neighborhood_name   TEXT,
    hybrid_score        DOUBLE PRECISION,
    total_monthly_cost  DOUBLE PRECISION,
    budget_status       TEXT,
    commute_minutes     INTEGER,

    -- Raw data blob
    raw_data            TEXT,

    -- Web app columns (new)
    status              TEXT NOT NULL DEFAULT 'active',
    favorited_at        TIMESTAMPTZ,
    dismissed_at        TIMESTAMPTZ,
    notified_at         TIMESTAMPTZ,
    status_updated_at   TIMESTAMPTZ,
    notes               TEXT
);

-- Pipeline run tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              TEXT PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    stage           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    stats           JSONB,
    error_message   TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_listings_hybrid_score ON listings (hybrid_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings (status);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings (source);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings (price);
CREATE INDEX IF NOT EXISTS idx_listings_scraped_at ON listings (scraped_at);
CREATE INDEX IF NOT EXISTS idx_listings_source_status ON listings (source, status);
CREATE INDEX IF NOT EXISTS idx_listings_notified ON listings (notified_at) WHERE notified_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs (started_at DESC);
