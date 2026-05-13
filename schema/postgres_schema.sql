BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_knowledge_to_book

CREATE TABLE projects (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    slug VARCHAR(160) NOT NULL, 
    description TEXT, 
    status VARCHAR(64) NOT NULL, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE TABLE book_volumes (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    subtitle VARCHAR(255), 
    slug VARCHAR(160) NOT NULL, 
    trim_size VARCHAR(64), 
    page_size VARCHAR(64), 
    binding_type VARCHAR(120), 
    printer_target VARCHAR(160), 
    status VARCHAR(64) NOT NULL, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    UNIQUE (project_id, slug)
);

CREATE TABLE source_materials (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    source_type VARCHAR(64) NOT NULL, 
    title VARCHAR(255), 
    location TEXT, 
    uri TEXT, 
    external_id VARCHAR(255), 
    provenance JSONB NOT NULL, 
    metadata JSONB NOT NULL, 
    content_hash VARCHAR(128), 
    status VARCHAR(64) NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE, 
    captured_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE knowledge_nodes (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    node_type VARCHAR(64) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    body TEXT NOT NULL, 
    confidence FLOAT NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE agent_runs (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    run_type VARCHAR(80) NOT NULL, 
    agent_name VARCHAR(160) NOT NULL, 
    tool_name VARCHAR(160), 
    prompt TEXT, 
    input_refs JSONB NOT NULL, 
    output_refs JSONB NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    error_message TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE tags (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    slug VARCHAR(120) NOT NULL, 
    description TEXT, 
    color VARCHAR(40), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    UNIQUE (project_id, slug)
);

CREATE TABLE field_note_candidates (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    thesis TEXT, 
    summary TEXT, 
    status VARCHAR(64) NOT NULL, 
    usefulness_score FLOAT, 
    specificity_score FLOAT, 
    novelty_score FLOAT, 
    groundedness_score FLOAT, 
    local_relevance_score FLOAT, 
    opinion_strength_score FLOAT, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE chapter_briefs (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    volume_id UUID, 
    title VARCHAR(255) NOT NULL, 
    subtitle VARCHAR(255), 
    slug VARCHAR(160) NOT NULL, 
    sequence_order INTEGER, 
    status VARCHAR(64) NOT NULL, 
    intended_page_count INTEGER, 
    target_word_count INTEGER, 
    situation TEXT, 
    "constraint" TEXT, 
    build TEXT, 
    pattern TEXT, 
    oahu_layer TEXT, 
    field_note TEXT, 
    next_build TEXT, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(volume_id) REFERENCES book_volumes (id) ON DELETE SET NULL, 
    UNIQUE (volume_id, slug)
);

CREATE TABLE node_source_links (
    id UUID NOT NULL, 
    node_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    locator_type VARCHAR(64), 
    locator_data JSONB NOT NULL, 
    quote TEXT, 
    excerpt TEXT, 
    relevance_score FLOAT, 
    confidence_score FLOAT, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_id) REFERENCES source_materials (id) ON DELETE CASCADE
);

CREATE TABLE knowledge_edges (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    source_node_id UUID NOT NULL, 
    target_node_id UUID NOT NULL, 
    edge_type VARCHAR(64) NOT NULL, 
    description TEXT, 
    confidence FLOAT NOT NULL, 
    evidence_link_id UUID, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(target_node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(evidence_link_id) REFERENCES node_source_links (id) ON DELETE SET NULL
);

CREATE TABLE field_note_candidate_nodes (
    id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    node_id UUID NOT NULL, 
    role VARCHAR(80), 
    sequence_order INTEGER, 
    relevance_score FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES field_note_candidates (id) ON DELETE CASCADE, 
    FOREIGN KEY(node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    UNIQUE (candidate_id, node_id)
);

CREATE TABLE chapter_brief_candidates (
    id UUID NOT NULL, 
    chapter_brief_id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    role VARCHAR(80), 
    sequence_order INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chapter_brief_id) REFERENCES chapter_briefs (id) ON DELETE CASCADE, 
    FOREIGN KEY(candidate_id) REFERENCES field_note_candidates (id) ON DELETE CASCADE, 
    UNIQUE (chapter_brief_id, candidate_id)
);

CREATE TABLE chapter_brief_nodes (
    id UUID NOT NULL, 
    chapter_brief_id UUID NOT NULL, 
    node_id UUID NOT NULL, 
    section_key VARCHAR(80), 
    sequence_order INTEGER, 
    relevance_score FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chapter_brief_id) REFERENCES chapter_briefs (id) ON DELETE CASCADE, 
    FOREIGN KEY(node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    UNIQUE (chapter_brief_id, node_id)
);

CREATE TABLE chapter_drafts (
    id UUID NOT NULL, 
    chapter_brief_id UUID NOT NULL, 
    agent_run_id UUID, 
    version_number INTEGER NOT NULL, 
    body_format VARCHAR(40) NOT NULL, 
    body TEXT NOT NULL, 
    model_provider VARCHAR(120), 
    model_name VARCHAR(160), 
    model_metadata JSONB NOT NULL, 
    generation_prompt_ref TEXT, 
    status VARCHAR(64) NOT NULL, 
    editor_notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chapter_brief_id) REFERENCES chapter_briefs (id) ON DELETE CASCADE, 
    FOREIGN KEY(agent_run_id) REFERENCES agent_runs (id) ON DELETE SET NULL, 
    UNIQUE (chapter_brief_id, version_number)
);

CREATE TABLE visual_assets (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    chapter_brief_id UUID, 
    chapter_draft_id UUID, 
    knowledge_node_id UUID, 
    source_id UUID, 
    asset_type VARCHAR(64) NOT NULL, 
    section_key VARCHAR(80), 
    path TEXT, 
    url TEXT, 
    prompt TEXT, 
    negative_prompt TEXT, 
    model_provider VARCHAR(120), 
    model_name VARCHAR(160), 
    generation_params JSONB NOT NULL, 
    license_status VARCHAR(120), 
    rights_metadata JSONB NOT NULL, 
    width INTEGER, 
    height INTEGER, 
    dpi INTEGER, 
    print_suitability_score FLOAT, 
    alt_text TEXT, 
    caption TEXT, 
    status VARCHAR(64) NOT NULL, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(chapter_brief_id) REFERENCES chapter_briefs (id) ON DELETE SET NULL, 
    FOREIGN KEY(chapter_draft_id) REFERENCES chapter_drafts (id) ON DELETE SET NULL, 
    FOREIGN KEY(knowledge_node_id) REFERENCES knowledge_nodes (id) ON DELETE SET NULL, 
    FOREIGN KEY(source_id) REFERENCES source_materials (id) ON DELETE SET NULL
);

CREATE TABLE rendered_outputs (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    volume_id UUID, 
    chapter_brief_id UUID, 
    output_type VARCHAR(64) NOT NULL, 
    renderer VARCHAR(120) NOT NULL, 
    config_path TEXT, 
    output_path TEXT NOT NULL, 
    git_commit_hash VARCHAR(80), 
    build_logs TEXT, 
    status VARCHAR(64) NOT NULL, 
    rendered_at TIMESTAMP WITH TIME ZONE, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(volume_id) REFERENCES book_volumes (id) ON DELETE SET NULL, 
    FOREIGN KEY(chapter_brief_id) REFERENCES chapter_briefs (id) ON DELETE SET NULL
);

CREATE TABLE evaluations (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    target_type VARCHAR(64) NOT NULL, 
    target_id UUID NOT NULL, 
    evaluator_type VARCHAR(64) NOT NULL, 
    evaluator_name VARCHAR(160), 
    rubric_name VARCHAR(120) NOT NULL, 
    scores JSONB NOT NULL, 
    comments TEXT, 
    status VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE taggings (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    tag_id UUID NOT NULL, 
    target_type VARCHAR(64) NOT NULL, 
    target_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE, 
    UNIQUE (tag_id, target_type, target_id)
);

CREATE INDEX ix_book_volumes_project_id ON book_volumes (project_id);

CREATE INDEX ix_source_materials_project_id ON source_materials (project_id);

CREATE INDEX ix_source_materials_source_type ON source_materials (source_type);

CREATE INDEX ix_source_materials_content_hash ON source_materials (content_hash);

CREATE INDEX ix_knowledge_nodes_project_id ON knowledge_nodes (project_id);

CREATE INDEX ix_knowledge_nodes_node_type ON knowledge_nodes (node_type);

CREATE INDEX ix_knowledge_nodes_status ON knowledge_nodes (status);

CREATE INDEX ix_agent_runs_project_id ON agent_runs (project_id);

CREATE INDEX ix_agent_runs_run_type ON agent_runs (run_type);

CREATE INDEX ix_agent_runs_status ON agent_runs (status);

CREATE INDEX ix_field_note_candidates_project_id ON field_note_candidates (project_id);

CREATE INDEX ix_field_note_candidates_status ON field_note_candidates (status);

CREATE INDEX ix_chapter_briefs_project_id ON chapter_briefs (project_id);

CREATE INDEX ix_chapter_briefs_volume_id ON chapter_briefs (volume_id);

CREATE INDEX ix_chapter_briefs_status ON chapter_briefs (status);

CREATE INDEX ix_node_source_links_node_id ON node_source_links (node_id);

CREATE INDEX ix_node_source_links_source_id ON node_source_links (source_id);

CREATE INDEX ix_knowledge_edges_project_id ON knowledge_edges (project_id);

CREATE INDEX ix_knowledge_edges_source_node_id ON knowledge_edges (source_node_id);

CREATE INDEX ix_knowledge_edges_target_node_id ON knowledge_edges (target_node_id);

CREATE INDEX ix_knowledge_edges_edge_type ON knowledge_edges (edge_type);

CREATE INDEX ix_knowledge_edges_evidence_link_id ON knowledge_edges (evidence_link_id);

CREATE INDEX ix_field_note_candidate_nodes_candidate_id ON field_note_candidate_nodes (candidate_id);

CREATE INDEX ix_field_note_candidate_nodes_node_id ON field_note_candidate_nodes (node_id);

CREATE INDEX ix_chapter_brief_candidates_chapter_brief_id ON chapter_brief_candidates (chapter_brief_id);

CREATE INDEX ix_chapter_brief_candidates_candidate_id ON chapter_brief_candidates (candidate_id);

CREATE INDEX ix_chapter_brief_nodes_chapter_brief_id ON chapter_brief_nodes (chapter_brief_id);

CREATE INDEX ix_chapter_brief_nodes_node_id ON chapter_brief_nodes (node_id);

CREATE INDEX ix_chapter_drafts_chapter_brief_id ON chapter_drafts (chapter_brief_id);

CREATE INDEX ix_chapter_drafts_agent_run_id ON chapter_drafts (agent_run_id);

CREATE INDEX ix_chapter_drafts_status ON chapter_drafts (status);

CREATE INDEX ix_visual_assets_project_id ON visual_assets (project_id);

CREATE INDEX ix_visual_assets_chapter_brief_id ON visual_assets (chapter_brief_id);

CREATE INDEX ix_visual_assets_chapter_draft_id ON visual_assets (chapter_draft_id);

CREATE INDEX ix_visual_assets_knowledge_node_id ON visual_assets (knowledge_node_id);

CREATE INDEX ix_visual_assets_source_id ON visual_assets (source_id);

CREATE INDEX ix_visual_assets_asset_type ON visual_assets (asset_type);

CREATE INDEX ix_visual_assets_status ON visual_assets (status);

CREATE INDEX ix_rendered_outputs_project_id ON rendered_outputs (project_id);

CREATE INDEX ix_rendered_outputs_volume_id ON rendered_outputs (volume_id);

CREATE INDEX ix_rendered_outputs_chapter_brief_id ON rendered_outputs (chapter_brief_id);

CREATE INDEX ix_rendered_outputs_output_type ON rendered_outputs (output_type);

CREATE INDEX ix_rendered_outputs_git_commit_hash ON rendered_outputs (git_commit_hash);

CREATE INDEX ix_rendered_outputs_status ON rendered_outputs (status);

CREATE INDEX ix_evaluations_project_id ON evaluations (project_id);

CREATE INDEX ix_evaluations_target_type ON evaluations (target_type);

CREATE INDEX ix_evaluations_target_id ON evaluations (target_id);

CREATE INDEX ix_evaluations_rubric_name ON evaluations (rubric_name);

CREATE INDEX ix_evaluations_status ON evaluations (status);

CREATE INDEX ix_tags_project_id ON tags (project_id);

CREATE INDEX ix_taggings_project_id ON taggings (project_id);

CREATE INDEX ix_taggings_tag_id ON taggings (tag_id);

CREATE INDEX ix_taggings_target_type ON taggings (target_type);

CREATE INDEX ix_taggings_target_id ON taggings (target_id);

INSERT INTO alembic_version (version_num) VALUES ('0001_knowledge_to_book') RETURNING alembic_version.version_num;

-- Running upgrade 0001_knowledge_to_book -> 0002_ingestion_review

CREATE TABLE source_chunks (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    chunk_type VARCHAR(64) NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    title VARCHAR(255), 
    text TEXT NOT NULL, 
    text_hash VARCHAR(128) NOT NULL, 
    locator_type VARCHAR(64), 
    locator_data JSONB NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    ocr_engine VARCHAR(160), 
    ocr_confidence FLOAT, 
    uncertainty_notes TEXT, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_id) REFERENCES source_materials (id) ON DELETE CASCADE, 
    UNIQUE (source_id, chunk_index)
);

CREATE TABLE extraction_runs (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    agent_run_id UUID, 
    provider VARCHAR(120) NOT NULL, 
    model VARCHAR(160) NOT NULL, 
    prompt_version VARCHAR(120) NOT NULL, 
    schema_version VARCHAR(120) NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    config JSONB NOT NULL, 
    usage JSONB NOT NULL, 
    error TEXT, 
    chunks_count INTEGER NOT NULL, 
    candidates_count INTEGER NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(agent_run_id) REFERENCES agent_runs (id) ON DELETE SET NULL
);

CREATE TABLE extracted_candidates (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    extraction_run_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    source_chunk_id UUID NOT NULL, 
    node_type VARCHAR(64) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    body TEXT NOT NULL, 
    confidence_score FLOAT NOT NULL, 
    reuse_score FLOAT NOT NULL, 
    evidence_quote TEXT, 
    rationale TEXT, 
    raw_output JSONB NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    promoted_node_id UUID, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_id) REFERENCES source_materials (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_chunk_id) REFERENCES source_chunks (id) ON DELETE CASCADE, 
    FOREIGN KEY(promoted_node_id) REFERENCES knowledge_nodes (id) ON DELETE SET NULL
);

CREATE TABLE extracted_candidate_edges (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    extraction_run_id UUID NOT NULL, 
    source_chunk_id UUID NOT NULL, 
    source_candidate_id UUID, 
    target_candidate_id UUID, 
    source_node_id UUID, 
    target_node_id UUID, 
    edge_type VARCHAR(64) NOT NULL, 
    rationale TEXT, 
    evidence_quote TEXT, 
    strength FLOAT NOT NULL, 
    confidence_score FLOAT NOT NULL, 
    status VARCHAR(64) NOT NULL, 
    promoted_edge_id UUID, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(extraction_run_id) REFERENCES extraction_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_chunk_id) REFERENCES source_chunks (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_candidate_id) REFERENCES extracted_candidates (id) ON DELETE CASCADE, 
    FOREIGN KEY(target_candidate_id) REFERENCES extracted_candidates (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(target_node_id) REFERENCES knowledge_nodes (id) ON DELETE CASCADE, 
    FOREIGN KEY(promoted_edge_id) REFERENCES knowledge_edges (id) ON DELETE SET NULL
);

CREATE TABLE review_decisions (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    decision_type VARCHAR(64) NOT NULL, 
    target_type VARCHAR(64) NOT NULL, 
    target_id UUID NOT NULL, 
    decision VARCHAR(64) NOT NULL, 
    reviewer VARCHAR(160) NOT NULL, 
    rationale TEXT, 
    applied_by VARCHAR(160), 
    dry_run BOOLEAN NOT NULL, 
    evidence JSONB NOT NULL, 
    metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_source_chunks_project_id ON source_chunks (project_id);

CREATE INDEX ix_source_chunks_source_id ON source_chunks (source_id);

CREATE INDEX ix_source_chunks_chunk_type ON source_chunks (chunk_type);

CREATE INDEX ix_source_chunks_text_hash ON source_chunks (text_hash);

CREATE INDEX ix_source_chunks_status ON source_chunks (status);

CREATE INDEX ix_extraction_runs_project_id ON extraction_runs (project_id);

CREATE INDEX ix_extraction_runs_agent_run_id ON extraction_runs (agent_run_id);

CREATE INDEX ix_extraction_runs_status ON extraction_runs (status);

CREATE INDEX ix_extracted_candidates_project_id ON extracted_candidates (project_id);

CREATE INDEX ix_extracted_candidates_extraction_run_id ON extracted_candidates (extraction_run_id);

CREATE INDEX ix_extracted_candidates_source_id ON extracted_candidates (source_id);

CREATE INDEX ix_extracted_candidates_source_chunk_id ON extracted_candidates (source_chunk_id);

CREATE INDEX ix_extracted_candidates_node_type ON extracted_candidates (node_type);

CREATE INDEX ix_extracted_candidates_status ON extracted_candidates (status);

CREATE INDEX ix_extracted_candidates_promoted_node_id ON extracted_candidates (promoted_node_id);

CREATE INDEX ix_extracted_candidate_edges_project_id ON extracted_candidate_edges (project_id);

CREATE INDEX ix_extracted_candidate_edges_extraction_run_id ON extracted_candidate_edges (extraction_run_id);

CREATE INDEX ix_extracted_candidate_edges_source_chunk_id ON extracted_candidate_edges (source_chunk_id);

CREATE INDEX ix_extracted_candidate_edges_source_candidate_id ON extracted_candidate_edges (source_candidate_id);

CREATE INDEX ix_extracted_candidate_edges_target_candidate_id ON extracted_candidate_edges (target_candidate_id);

CREATE INDEX ix_extracted_candidate_edges_source_node_id ON extracted_candidate_edges (source_node_id);

CREATE INDEX ix_extracted_candidate_edges_target_node_id ON extracted_candidate_edges (target_node_id);

CREATE INDEX ix_extracted_candidate_edges_edge_type ON extracted_candidate_edges (edge_type);

CREATE INDEX ix_extracted_candidate_edges_status ON extracted_candidate_edges (status);

CREATE INDEX ix_extracted_candidate_edges_promoted_edge_id ON extracted_candidate_edges (promoted_edge_id);

CREATE INDEX ix_review_decisions_project_id ON review_decisions (project_id);

CREATE INDEX ix_review_decisions_decision_type ON review_decisions (decision_type);

CREATE INDEX ix_review_decisions_target_type ON review_decisions (target_type);

CREATE INDEX ix_review_decisions_target_id ON review_decisions (target_id);

UPDATE alembic_version SET version_num='0002_ingestion_review' WHERE alembic_version.version_num = '0001_knowledge_to_book';

COMMIT;

