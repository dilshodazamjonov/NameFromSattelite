CREATE TABLE places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT DEFAULT 'Uzbekistan',
    region TEXT NULL,
    city TEXT NULL,
    latitude DOUBLE PRECISION NULL,
    longitude DOUBLE PRECISION NULL,
    note TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE letter_images (
    id TEXT PRIMARY KEY,
    letter TEXT NOT NULL,
    original_filename TEXT NULL,
    storage_key TEXT NOT NULL,
    image_path TEXT NOT NULL,
    public_url TEXT NOT NULL,
    source_type TEXT DEFAULT 'manual_satellite',
    place_id TEXT NULL REFERENCES places(id),
    note TEXT NULL,
    beauty_score INTEGER NULL,
    readability_score INTEGER NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_letter_images_letter ON letter_images(letter);
CREATE INDEX idx_letter_images_place_id ON letter_images(place_id);

-- Legacy SQLite classifier tables may still exist in backend/data/app.db.
-- They are not the main metadata source for the manual-label MVP.
