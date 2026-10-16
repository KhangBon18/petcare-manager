-- Schema cơ sở dữ liệu PetCare Manager
-- Kích hoạt khóa ngoại được thực hiện trong connection: PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'staff')),
    full_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS owners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES owners(id),
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    sex TEXT NOT NULL CHECK(sex IN ('male', 'female', 'unknown')),
    birth_date TEXT,
    weight_kg REAL CHECK(weight_kg IS NULL OR weight_kg >= 0),
    coat_color TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    price_vnd INTEGER NOT NULL CHECK(price_vnd >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    service_id INTEGER NOT NULL REFERENCES services(id),
    performed_at TEXT NOT NULL,
    unit_price_vnd INTEGER NOT NULL CHECK(unit_price_vnd >= 0),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS examinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    visit_id INTEGER NOT NULL UNIQUE REFERENCES service_visits(id),
    exam_date TEXT NOT NULL,
    symptoms TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    medicines TEXT
);

CREATE TABLE IF NOT EXISTS vaccinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    visit_id INTEGER NOT NULL UNIQUE REFERENCES service_visits(id),
    vaccine_name TEXT NOT NULL,
    injection_date TEXT NOT NULL,
    next_due_date TEXT,
    reminder_resolved INTEGER NOT NULL DEFAULT 0 CHECK(reminder_resolved IN (0, 1))
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    type TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('planned', 'completed', 'cancelled')) DEFAULT 'planned',
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES owners(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('unpaid', 'paid', 'cancelled')) DEFAULT 'unpaid',
    paid_at TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    visit_id INTEGER NOT NULL UNIQUE REFERENCES service_visits(id),
    service_name_snapshot TEXT NOT NULL,
    pet_name_snapshot TEXT NOT NULL,
    amount_vnd INTEGER NOT NULL CHECK(amount_vnd >= 0)
);

-- Chỉ mục tối ưu hóa truy vấn
CREATE INDEX IF NOT EXISTS idx_pets_owner_id ON pets(owner_id);
CREATE INDEX IF NOT EXISTS idx_service_visits_pet_id ON service_visits(pet_id);
CREATE INDEX IF NOT EXISTS idx_service_visits_service_id ON service_visits(service_id);
CREATE INDEX IF NOT EXISTS idx_examinations_pet_id ON examinations(pet_id);
CREATE INDEX IF NOT EXISTS idx_vaccinations_pet_id ON vaccinations(pet_id);
CREATE INDEX IF NOT EXISTS idx_appointments_pet_id ON appointments(pet_id);
CREATE INDEX IF NOT EXISTS idx_invoices_owner_id ON invoices(owner_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status_paid_at ON invoices(status, paid_at);
