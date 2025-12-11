-- Bug Deduplication System Database Schema

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main bugs table
CREATE TABLE IF NOT EXISTS bugs (
    id SERIAL PRIMARY KEY,
    
    -- Core bug information
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    repro_steps TEXT,
    logs TEXT,
    
    -- Metadata
    severity VARCHAR(20),
    priority VARCHAR(20),
    status VARCHAR(50) DEFAULT 'New',
    assignee VARCHAR(100),
    reporter VARCHAR(100) NOT NULL,
    
    -- Environment information
    device VARCHAR(100),
    os_version VARCHAR(50),
    build_version VARCHAR(50),
    region VARCHAR(10),
    
    -- AI-driven fields
    embedding vector(384),
    parent_bug_id INTEGER REFERENCES bugs(id),
    match_score FLOAT,
    classification_tag VARCHAR(50),
    
    -- External system IDs
    jira_key VARCHAR(50) UNIQUE,
    tp_id VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Indexes for bugs table
CREATE INDEX idx_bugs_title ON bugs(title);
CREATE INDEX idx_bugs_status ON bugs(status);
CREATE INDEX idx_bugs_build_version ON bugs(build_version);
CREATE INDEX idx_bugs_region ON bugs(region);
CREATE INDEX idx_bugs_parent_bug_id ON bugs(parent_bug_id);
CREATE INDEX idx_bugs_classification_tag ON bugs(classification_tag);
CREATE INDEX idx_bugs_jira_key ON bugs(jira_key);
CREATE INDEX idx_bugs_tp_id ON bugs(tp_id);
CREATE INDEX idx_bugs_created_at ON bugs(created_at);

-- Vector similarity index (HNSW for faster similarity search)
CREATE INDEX idx_bugs_embedding ON bugs USING hnsw (embedding vector_cosine_ops);

-- Low quality queue table
CREATE TABLE IF NOT EXISTS low_quality_queue (
    id SERIAL PRIMARY KEY,
    
    -- Original submission data
    title VARCHAR(500) NOT NULL,
    description TEXT,
    repro_steps TEXT,
    logs TEXT,
    
    -- Metadata
    reporter VARCHAR(100) NOT NULL,
    device VARCHAR(100),
    build_version VARCHAR(50),
    region VARCHAR(10),
    
    -- Quality issues
    quality_issues JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'Pending',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    -- If approved, the created bug ID
    created_bug_id INTEGER REFERENCES bugs(id),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_low_quality_status ON low_quality_queue(status);
CREATE INDEX idx_low_quality_created_at ON low_quality_queue(created_at);

-- Duplicate history table
CREATE TABLE IF NOT EXISTS duplicate_history (
    id SERIAL PRIMARY KEY,
    
    -- The duplicate bug (may or may not be created based on threshold)
    duplicate_bug_id INTEGER REFERENCES bugs(id),
    
    -- The original parent bug
    parent_bug_id INTEGER REFERENCES bugs(id) NOT NULL,
    
    -- Match details
    match_score FLOAT NOT NULL,
    match_method VARCHAR(50),
    
    -- Original submission data (even if blocked)
    submission_data JSONB,
    
    -- User who submitted
    submitted_by VARCHAR(100),
    
    -- Was this blocked from creation?
    was_blocked BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_duplicate_history_duplicate_bug_id ON duplicate_history(duplicate_bug_id);
CREATE INDEX idx_duplicate_history_parent_bug_id ON duplicate_history(parent_bug_id);
CREATE INDEX idx_duplicate_history_detected_at ON duplicate_history(detected_at);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    
    -- Event type
    event_type VARCHAR(100) NOT NULL,
    
    -- Related entities
    bug_id INTEGER REFERENCES bugs(id),
    parent_bug_id INTEGER REFERENCES bugs(id),
    low_quality_id INTEGER REFERENCES low_quality_queue(id),
    
    -- User who triggered the action
    "user" VARCHAR(100),
    
    -- AI decision details
    ai_confidence FLOAT,
    ai_reasoning JSONB,
    
    -- Before/After state for overrides
    previous_state JSONB,
    new_state JSONB,
    
    -- Additional context
    metadata JSONB,
    notes TEXT,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_log_bug_id ON audit_log(bug_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- System metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    
    -- Metric details
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT,
    
    -- Dimensions
    region VARCHAR(10),
    build_version VARCHAR(50),
    time_period VARCHAR(20),
    
    -- Additional data
    metadata JSONB,
    
    -- Timestamp
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_system_metrics_metric_name ON system_metrics(metric_name);
CREATE INDEX idx_system_metrics_recorded_at ON system_metrics(recorded_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_bugs_updated_at BEFORE UPDATE ON bugs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
