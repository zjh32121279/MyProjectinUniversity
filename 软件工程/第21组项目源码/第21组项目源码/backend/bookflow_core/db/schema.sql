-- BookFlow database schema: bookflow
-- Generated from SQLAlchemy Declarative models.
PRAGMA foreign_keys=ON;


CREATE TABLE action_snapshots (
	id INTEGER NOT NULL, 
	snapshot_code VARCHAR, 
	audit_event_id INTEGER, 
	action_type VARCHAR, 
	target_entity_type VARCHAR, 
	target_entity_id INTEGER, 
	before_json TEXT, 
	after_json TEXT, 
	can_rollback BOOLEAN, 
	rolled_back BOOLEAN, 
	rolled_back_by_admin_id INTEGER, 
	rolled_back_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (snapshot_code), 
	FOREIGN KEY(audit_event_id) REFERENCES audit_events (id), 
	FOREIGN KEY(rolled_back_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE admin_login_events (
	id INTEGER NOT NULL, 
	admin_id INTEGER, 
	admin_code VARCHAR, 
	event_type VARCHAR, 
	ip_address VARCHAR, 
	user_agent VARCHAR, 
	result VARCHAR, 
	failure_reason VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_id) REFERENCES admin_users (id)
);


CREATE TABLE admin_permissions (
	id INTEGER NOT NULL, 
	permission_code VARCHAR, 
	name VARCHAR, 
	module VARCHAR, 
	description TEXT, 
	risk_level VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (permission_code)
);


CREATE TABLE admin_role_permissions (
	id INTEGER NOT NULL, 
	role_id INTEGER, 
	permission_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES admin_roles (id), 
	FOREIGN KEY(permission_id) REFERENCES admin_permissions (id)
);


CREATE TABLE admin_roles (
	id INTEGER NOT NULL, 
	role_code VARCHAR, 
	name VARCHAR, 
	description TEXT, 
	is_system BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (role_code)
);


CREATE TABLE admin_user_roles (
	id INTEGER NOT NULL, 
	admin_id INTEGER, 
	role_id INTEGER, 
	assigned_by_admin_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(role_id) REFERENCES admin_roles (id), 
	FOREIGN KEY(assigned_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE admin_users (
	id INTEGER NOT NULL, 
	source_admin_id INTEGER, 
	admin_code VARCHAR, 
	name VARCHAR, 
	email VARCHAR, 
	password_hash VARCHAR, 
	status VARCHAR, 
	is_super_admin BOOLEAN, 
	last_login_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE agent_runs (
	id INTEGER NOT NULL, 
	run_code VARCHAR, 
	trigger_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_type VARCHAR, 
	actor_code VARCHAR, 
	tool_name VARCHAR, 
	status VARCHAR, 
	input_json TEXT, 
	output_json TEXT, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (run_code), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE agent_steps (
	id INTEGER NOT NULL, 
	run_id INTEGER, 
	step_name VARCHAR, 
	status VARCHAR, 
	detail_json TEXT, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_id) REFERENCES agent_runs (id)
);


CREATE TABLE ai_approval_requests (
	id INTEGER NOT NULL, 
	approval_code VARCHAR, 
	run_id INTEGER, 
	capability_id INTEGER, 
	requested_action VARCHAR, 
	payload_json TEXT, 
	status VARCHAR, 
	requested_by_agent_run_id INTEGER, 
	reviewed_by_admin_id INTEGER, 
	reviewed_at DATETIME, 
	decision_reason TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (approval_code), 
	FOREIGN KEY(run_id) REFERENCES agent_runs (id), 
	FOREIGN KEY(capability_id) REFERENCES ai_capabilities (id), 
	FOREIGN KEY(requested_by_agent_run_id) REFERENCES agent_runs (id), 
	FOREIGN KEY(reviewed_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE ai_capabilities (
	id INTEGER NOT NULL, 
	tool_name VARCHAR, 
	display_name VARCHAR, 
	permission_level VARCHAR, 
	risk_level VARCHAR, 
	is_write BOOLEAN, 
	writes_db BOOLEAN, 
	requires_super_authorization BOOLEAN, 
	input_schema_json TEXT, 
	output_schema_json TEXT, 
	is_enabled BOOLEAN, 
	description TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE ai_chat_messages (
	id INTEGER NOT NULL, 
	conversation_id INTEGER, 
	role VARCHAR, 
	content TEXT, 
	agent_run_id INTEGER, 
	token_usage_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id), 
	FOREIGN KEY(agent_run_id) REFERENCES agent_runs (id), 
	FOREIGN KEY(token_usage_id) REFERENCES ai_token_usage (id)
);


CREATE TABLE ai_conversations (
	id INTEGER NOT NULL, 
	conversation_code VARCHAR, 
	actor_admin_id INTEGER, 
	actor_type VARCHAR, 
	actor_code VARCHAR, 
	title VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (conversation_code), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE ai_memory_items (
	id INTEGER NOT NULL, 
	memory_code VARCHAR, 
	scope VARCHAR, 
	"key" VARCHAR, 
	value_json TEXT, 
	importance INTEGER, 
	last_used_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (memory_code)
);


CREATE TABLE ai_observations (
	id INTEGER NOT NULL, 
	observation_code VARCHAR, 
	source_type VARCHAR, 
	source_entity_type VARCHAR, 
	source_entity_id INTEGER, 
	payload_json TEXT, 
	status VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (observation_code)
);


CREATE TABLE ai_rule_execution_logs (
	id INTEGER NOT NULL, 
	rule_id INTEGER, 
	rule_version_id INTEGER, 
	related_entity_type VARCHAR, 
	related_entity_id INTEGER, 
	trigger_result VARCHAR, 
	action_result VARCHAR, 
	actor_agent_run_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(rule_id) REFERENCES ai_rules (id), 
	FOREIGN KEY(rule_version_id) REFERENCES ai_rule_versions (id), 
	FOREIGN KEY(actor_agent_run_id) REFERENCES agent_runs (id)
);


CREATE TABLE ai_rule_versions (
	id INTEGER NOT NULL, 
	rule_id INTEGER, 
	version_no INTEGER, 
	rule_config_json TEXT, 
	trigger_condition_json TEXT, 
	action_json TEXT, 
	effective_from DATE, 
	effective_to DATE, 
	created_by_admin_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(rule_id) REFERENCES ai_rules (id), 
	FOREIGN KEY(created_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE ai_rules (
	id INTEGER NOT NULL, 
	rule_code VARCHAR, 
	rule_name VARCHAR, 
	rule_type VARCHAR, 
	module VARCHAR, 
	target_reader_type VARCHAR, 
	target_circulation_type VARCHAR, 
	priority INTEGER, 
	risk_level VARCHAR, 
	status VARCHAR, 
	is_enabled BOOLEAN, 
	current_version_id INTEGER, 
	created_by_admin_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (rule_code), 
	FOREIGN KEY(current_version_id) REFERENCES ai_rule_versions (id), 
	FOREIGN KEY(created_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE ai_token_usage (
	id INTEGER NOT NULL, 
	provider VARCHAR, 
	model VARCHAR, 
	prompt_tokens INTEGER, 
	completion_tokens INTEGER, 
	total_tokens INTEGER, 
	cost_estimate FLOAT, 
	related_run_id INTEGER, 
	related_conversation_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(related_run_id) REFERENCES agent_runs (id), 
	FOREIGN KEY(related_conversation_id) REFERENCES ai_conversations (id)
);


CREATE TABLE analytics_snapshots (
	id INTEGER NOT NULL, 
	snapshot_code VARCHAR, 
	snapshot_date DATE, 
	module VARCHAR, 
	payload_json TEXT, 
	generated_by VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (snapshot_code)
);


CREATE TABLE audit_events (
	id INTEGER NOT NULL, 
	audit_code VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	actor_agent_run_id INTEGER, 
	action VARCHAR, 
	target_entity_type VARCHAR, 
	target_entity_id INTEGER, 
	result VARCHAR, 
	ip_address VARCHAR, 
	user_agent VARCHAR, 
	request_id INTEGER, 
	detail_json TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (audit_code), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(actor_agent_run_id) REFERENCES agent_runs (id)
);
CREATE INDEX ix_audit_events_action_created ON audit_events (action, created_at);


CREATE TABLE book_categories (
	id INTEGER NOT NULL, 
	category_code VARCHAR, 
	category_name VARCHAR, 
	subcategory_examples VARCHAR, 
	book_title_count INTEGER, 
	copy_count INTEGER, 
	primary_zone_id INTEGER, 
	primary_zone_code VARCHAR, 
	clc_hint VARCHAR, 
	sort_order INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(primary_zone_id) REFERENCES library_zones (id)
);


CREATE TABLE book_circulation_stats (
	id INTEGER NOT NULL, 
	book_id INTEGER, 
	source_book_id INTEGER, 
	title_snapshot VARCHAR, 
	total_copies INTEGER, 
	available_copies INTEGER, 
	active_loans INTEGER, 
	reservations_waiting INTEGER, 
	borrow_90d INTEGER, 
	reserve_90d INTEGER, 
	borrow_365d INTEGER, 
	days_since_last_borrow INTEGER, 
	circulation_type VARCHAR, 
	last_borrow_date DATE, 
	stat_date DATE, 
	computed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(book_id) REFERENCES books (id)
);


CREATE TABLE book_copies (
	id INTEGER NOT NULL, 
	source_copy_id INTEGER, 
	copy_code VARCHAR, 
	source_book_id INTEGER, 
	book_id INTEGER, 
	copy_no INTEGER, 
	barcode VARCHAR, 
	category_code VARCHAR, 
	subcategory_code VARCHAR, 
	collection_type VARCHAR, 
	can_borrow_outside_library BOOLEAN, 
	status_code VARCHAR, 
	status_name VARCHAR, 
	copy_status VARCHAR, 
	current_zone_id INTEGER, 
	current_zone_code VARCHAR, 
	current_shelf_id INTEGER, 
	shelf_code VARCHAR, 
	current_position_id INTEGER, 
	shelf_position VARCHAR, 
	home_zone_id INTEGER, 
	home_zone_code VARCHAR, 
	home_shelf_id INTEGER, 
	home_shelf_code VARCHAR, 
	home_position_id INTEGER, 
	home_shelf_position VARCHAR, 
	acquisition_date DATE, 
	acquisition_source VARCHAR, 
	condition_level VARCHAR, 
	asset_price_yuan FLOAT, 
	remark TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (copy_code), 
	FOREIGN KEY(book_id) REFERENCES books (id), 
	UNIQUE (barcode), 
	FOREIGN KEY(current_zone_id) REFERENCES library_zones (id), 
	FOREIGN KEY(current_shelf_id) REFERENCES shelves (id), 
	FOREIGN KEY(current_position_id) REFERENCES shelf_positions (id), 
	FOREIGN KEY(home_zone_id) REFERENCES library_zones (id), 
	FOREIGN KEY(home_shelf_id) REFERENCES shelves (id), 
	FOREIGN KEY(home_position_id) REFERENCES shelf_positions (id)
);
CREATE INDEX ix_book_copies_book_status ON book_copies (book_id, copy_status);
CREATE INDEX ix_book_copies_position_status ON book_copies (current_position_id, copy_status);


CREATE TABLE book_subcategories (
	id INTEGER NOT NULL, 
	subcategory_code VARCHAR, 
	subcategory_name VARCHAR, 
	category_id INTEGER, 
	category_code VARCHAR, 
	category_name VARCHAR, 
	allocated_book_title_count INTEGER, 
	sort_order INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (subcategory_code), 
	FOREIGN KEY(category_id) REFERENCES book_categories (id)
);


CREATE TABLE book_subject_relations (
	id INTEGER NOT NULL, 
	book_id INTEGER, 
	tag_id INTEGER, 
	weight VARCHAR, 
	source VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(book_id) REFERENCES books (id), 
	FOREIGN KEY(tag_id) REFERENCES book_subject_tags (id)
);


CREATE TABLE book_subject_tags (
	id INTEGER NOT NULL, 
	tag_name VARCHAR, 
	tag_type VARCHAR, 
	normalized_name VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (tag_name)
);


CREATE TABLE books (
	id INTEGER NOT NULL, 
	source_book_id INTEGER, 
	book_code VARCHAR, 
	category_id INTEGER, 
	category_code VARCHAR, 
	category_name VARCHAR, 
	subcategory_id INTEGER, 
	subcategory_code VARCHAR, 
	subcategory_name VARCHAR, 
	clc_hint VARCHAR, 
	title VARCHAR, 
	author VARCHAR, 
	publisher VARCHAR, 
	publish_year INTEGER, 
	isbn VARCHAR, 
	language VARCHAR, 
	edition VARCHAR, 
	pages INTEGER, 
	price_yuan FLOAT, 
	copy_count_snapshot VARCHAR, 
	primary_zone_id INTEGER, 
	primary_zone_code VARCHAR, 
	recommended_reader VARCHAR, 
	keywords VARCHAR, 
	introduction TEXT, 
	circulation_type VARCHAR, 
	data_note VARCHAR, 
	clc_code VARCHAR, 
	call_number VARCHAR, 
	isbn_status VARCHAR, 
	bibliographic_status VARCHAR, 
	book_source_class VARCHAR, 
	cover_url VARCHAR, 
	cover_source VARCHAR, 
	cover_status VARCHAR, 
	cover_updated_at DATETIME, 
	status VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (book_code), 
	FOREIGN KEY(category_id) REFERENCES book_categories (id), 
	FOREIGN KEY(subcategory_id) REFERENCES book_subcategories (id), 
	FOREIGN KEY(primary_zone_id) REFERENCES library_zones (id)
);
CREATE INDEX ix_books_category_status ON books (category_id, status);
CREATE INDEX ix_books_title_author_code ON books (title, author, book_code);


CREATE TABLE circulation_policies (
	id INTEGER NOT NULL, 
	hot_borrow_90d_threshold VARCHAR, 
	hot_reserve_90d_threshold VARCHAR, 
	cold_borrow_365d_threshold VARCHAR, 
	cold_days_since_last_borrow_threshold VARCHAR, 
	reservation_hold_days INTEGER, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE circulation_rules (
	id INTEGER NOT NULL, 
	rule_code VARCHAR, 
	reader_type_code VARCHAR, 
	reader_type_name VARCHAR, 
	circulation_type VARCHAR, 
	max_borrow_count INTEGER, 
	borrow_days INTEGER, 
	max_renewals INTEGER, 
	reservation_limit INTEGER, 
	is_active BOOLEAN, 
	effective_from DATE, 
	effective_to DATE, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (rule_code)
);


CREATE TABLE copy_location_events (
	id INTEGER NOT NULL, 
	copy_id INTEGER, 
	from_position_id INTEGER, 
	to_position_id INTEGER, 
	from_zone_id INTEGER, 
	to_zone_id INTEGER, 
	reason VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	actor_agent_run_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(copy_id) REFERENCES book_copies (id), 
	FOREIGN KEY(from_position_id) REFERENCES shelf_positions (id), 
	FOREIGN KEY(to_position_id) REFERENCES shelf_positions (id), 
	FOREIGN KEY(from_zone_id) REFERENCES library_zones (id), 
	FOREIGN KEY(to_zone_id) REFERENCES library_zones (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(actor_agent_run_id) REFERENCES agent_runs (id)
);


CREATE TABLE copy_status_events (
	id INTEGER NOT NULL, 
	copy_id INTEGER, 
	old_status VARCHAR, 
	new_status VARCHAR, 
	reason VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	actor_agent_run_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(copy_id) REFERENCES book_copies (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(actor_agent_run_id) REFERENCES agent_runs (id)
);


CREATE TABLE daily_operation_metrics (
	id INTEGER NOT NULL, 
	metric_date DATE, 
	metric_key VARCHAR, 
	metric_value VARCHAR, 
	metric_unit VARCHAR, 
	source_table VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE data_import_batches (
	id INTEGER NOT NULL, 
	batch_code VARCHAR, 
	source_name VARCHAR, 
	source_version VARCHAR, 
	file_name VARCHAR, 
	row_count INTEGER, 
	status VARCHAR, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_by_admin_id INTEGER, 
	note TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (batch_code)
);


CREATE TABLE data_import_errors (
	id INTEGER NOT NULL, 
	batch_id INTEGER, 
	file_name VARCHAR, 
	row_no INTEGER, 
	source_key VARCHAR, 
	error_type VARCHAR, 
	error_message TEXT, 
	raw_json TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(batch_id) REFERENCES data_import_batches (id)
);


CREATE TABLE export_jobs (
	id INTEGER NOT NULL, 
	export_code VARCHAR, 
	export_type VARCHAR, 
	template_name VARCHAR, 
	requester_admin_id INTEGER, 
	status VARCHAR, 
	filter_json TEXT, 
	file_path VARCHAR, 
	file_hash VARCHAR, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (export_code), 
	FOREIGN KEY(requester_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE library_profiles (
	id INTEGER NOT NULL, 
	library_code VARCHAR, 
	library_name VARCHAR, 
	library_type VARCHAR, 
	service_population VARCHAR, 
	building_area_sqm FLOAT, 
	open_floors VARCHAR, 
	paper_collection_count INTEGER, 
	lendable_collection_count INTEGER, 
	in_library_reference_count INTEGER, 
	periodical_count INTEGER, 
	reading_seat_count INTEGER, 
	shelf_count INTEGER, 
	registered_reader_count INTEGER, 
	monthly_active_reader_count INTEGER, 
	weekday_daily_visits VARCHAR, 
	weekend_daily_visits VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (library_code)
);


CREATE TABLE library_zones (
	id INTEGER NOT NULL, 
	zone_code VARCHAR, 
	zone_name VARCHAR, 
	floor VARCHAR, 
	area_sqm FLOAT, 
	main_use VARCHAR, 
	is_public BOOLEAN, 
	sort_order INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE loan_events (
	id INTEGER NOT NULL, 
	loan_id INTEGER, 
	event_type VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	event_time VARCHAR, 
	detail TEXT, 
	old_due_at DATETIME, 
	new_due_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(loan_id) REFERENCES loans (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE loans (
	id INTEGER NOT NULL, 
	source_loan_id INTEGER, 
	loan_code VARCHAR, 
	reader_id INTEGER, 
	source_reader_id INTEGER, 
	copy_id INTEGER, 
	source_copy_id INTEGER, 
	book_id INTEGER, 
	source_book_id INTEGER, 
	borrowed_at DATETIME, 
	due_at DATETIME, 
	returned_at DATETIME, 
	status VARCHAR, 
	renewal_count INTEGER, 
	overdue_days_snapshot INTEGER, 
	handled_by_admin_id INTEGER, 
	handled_by_code VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (loan_code), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(copy_id) REFERENCES book_copies (id), 
	FOREIGN KEY(book_id) REFERENCES books (id), 
	FOREIGN KEY(handled_by_admin_id) REFERENCES admin_users (id)
);
CREATE INDEX ix_loans_book_status ON loans (book_id, status);
CREATE INDEX ix_loans_copy_status ON loans (copy_id, status);
CREATE INDEX ix_loans_reader_status ON loans (reader_id, status);


CREATE TABLE notification_batches (
	id INTEGER NOT NULL, 
	batch_code VARCHAR, 
	template_id INTEGER, 
	title VARCHAR, 
	channel VARCHAR, 
	status VARCHAR, 
	created_by_admin_id INTEGER, 
	created_by_code VARCHAR, 
	target_count INTEGER, 
	sent_count INTEGER, 
	failed_count INTEGER, 
	send_at DATETIME, 
	sent_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (batch_code), 
	FOREIGN KEY(template_id) REFERENCES notification_templates (id), 
	FOREIGN KEY(created_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE notification_templates (
	id INTEGER NOT NULL, 
	template_code VARCHAR, 
	title_template VARCHAR, 
	content_template VARCHAR, 
	notification_type VARCHAR, 
	channel VARCHAR, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (template_code)
);


CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	notification_code VARCHAR, 
	batch_id INTEGER, 
	template_id INTEGER, 
	recipient_reader_id INTEGER, 
	recipient_admin_id INTEGER, 
	title VARCHAR, 
	content TEXT, 
	notification_type VARCHAR, 
	channel VARCHAR, 
	status VARCHAR, 
	related_entity_type VARCHAR, 
	related_entity_id INTEGER, 
	send_at DATETIME, 
	sent_at DATETIME, 
	read_at DATETIME, 
	failed_reason VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (notification_code), 
	FOREIGN KEY(batch_id) REFERENCES notification_batches (id), 
	FOREIGN KEY(template_id) REFERENCES notification_templates (id), 
	FOREIGN KEY(recipient_reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(recipient_admin_id) REFERENCES admin_users (id)
);
CREATE INDEX ix_notifications_admin_status ON notifications (recipient_admin_id, status);
CREATE INDEX ix_notifications_reader_status ON notifications (recipient_reader_id, status);


CREATE TABLE overdue_cases (
	id INTEGER NOT NULL, 
	loan_id INTEGER, 
	reader_id INTEGER, 
	copy_id INTEGER, 
	overdue_start_at DATETIME, 
	overdue_days INTEGER, 
	penalty_score INTEGER, 
	status VARCHAR, 
	resolved_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(loan_id) REFERENCES loans (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(copy_id) REFERENCES book_copies (id)
);


CREATE TABLE reader_accounts (
	id INTEGER NOT NULL, 
	source_reader_id INTEGER, 
	reader_code VARCHAR, 
	reader_type_code VARCHAR, 
	reader_type_name VARCHAR, 
	name VARCHAR, 
	phone_masked VARCHAR, 
	phone_hash VARCHAR, 
	email VARCHAR, 
	avatar_url VARCHAR, 
	status VARCHAR, 
	credit_score VARCHAR, 
	registered_at DATETIME, 
	active_90d VARCHAR, 
	current_borrow_count INTEGER, 
	borrow_suspended_until VARCHAR, 
	remark TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (reader_code)
);


CREATE TABLE reader_credentials (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	login_name VARCHAR, 
	phone_hash VARCHAR, 
	email VARCHAR, 
	password_hash VARCHAR, 
	status VARCHAR, 
	last_login_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id)
);


CREATE TABLE reader_credit_events (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	delta VARCHAR, 
	old_score VARCHAR, 
	new_score VARCHAR, 
	reason VARCHAR, 
	related_loan_id INTEGER, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(related_loan_id) REFERENCES loans (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE reader_login_events (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	login_name VARCHAR, 
	event_type VARCHAR, 
	ip_address VARCHAR, 
	user_agent VARCHAR, 
	result VARCHAR, 
	failure_reason VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id)
);


CREATE TABLE reader_notification_settings (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	borrow_due_enabled BOOLEAN, 
	reservation_arrival_enabled BOOLEAN, 
	system_notice_enabled BOOLEAN, 
	email_enabled BOOLEAN, 
	sms_enabled BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id)
);


CREATE TABLE reader_stats (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	active_loans VARCHAR, 
	overdue_count INTEGER, 
	total_borrow_count INTEGER, 
	total_reservation_count INTEGER, 
	last_borrowed_at DATETIME, 
	computed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id)
);


CREATE TABLE reader_status_events (
	id INTEGER NOT NULL, 
	reader_id INTEGER, 
	old_status VARCHAR, 
	new_status VARCHAR, 
	reason VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE reader_verification_codes (
	id INTEGER NOT NULL, 
	account VARCHAR, 
	purpose VARCHAR, 
	code_hash VARCHAR, 
	expire_at DATETIME, 
	consumed_at DATETIME, 
	request_ip VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);


CREATE TABLE reservation_events (
	id INTEGER NOT NULL, 
	reservation_id INTEGER, 
	event_type VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	event_time VARCHAR, 
	detail TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reservation_id) REFERENCES reservations (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE reservations (
	id INTEGER NOT NULL, 
	source_reservation_id INTEGER, 
	reservation_code VARCHAR, 
	reader_id INTEGER, 
	source_reader_id INTEGER, 
	book_id INTEGER, 
	source_book_id INTEGER, 
	fulfilled_copy_id INTEGER, 
	source_copy_id INTEGER, 
	status VARCHAR, 
	requested_at DATETIME, 
	reserved_until VARCHAR, 
	pickup_zone_id INTEGER, 
	pickup_zone_code VARCHAR, 
	pickup_position_id INTEGER, 
	pickup_shelf_position VARCHAR, 
	created_by_admin_id INTEGER, 
	created_by_code VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (reservation_code), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(book_id) REFERENCES books (id), 
	FOREIGN KEY(fulfilled_copy_id) REFERENCES book_copies (id), 
	FOREIGN KEY(pickup_zone_id) REFERENCES library_zones (id), 
	FOREIGN KEY(pickup_position_id) REFERENCES shelf_positions (id), 
	FOREIGN KEY(created_by_admin_id) REFERENCES admin_users (id)
);
CREATE INDEX ix_reservations_book_status ON reservations (book_id, status);
CREATE INDEX ix_reservations_reader_status ON reservations (reader_id, status);


CREATE TABLE review_items (
	id INTEGER NOT NULL, 
	review_code VARCHAR, 
	review_type VARCHAR, 
	title VARCHAR, 
	description TEXT, 
	status VARCHAR, 
	risk_level VARCHAR, 
	source_type VARCHAR, 
	requested_by_actor_type VARCHAR, 
	requested_by_admin_id INTEGER, 
	requested_by_agent_run_id INTEGER, 
	reviewed_by_admin_id INTEGER, 
	payload_json TEXT, 
	decision_reason TEXT, 
	created_at DATETIME, 
	reviewed_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (review_code), 
	FOREIGN KEY(requested_by_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(requested_by_agent_run_id) REFERENCES agent_runs (id), 
	FOREIGN KEY(reviewed_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE risk_events (
	id INTEGER NOT NULL, 
	warning_id INTEGER, 
	event_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_code VARCHAR, 
	detail TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(warning_id) REFERENCES risk_warnings (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE risk_warnings (
	id INTEGER NOT NULL, 
	source_risk_id INTEGER, 
	warning_code VARCHAR, 
	warning_type VARCHAR, 
	severity VARCHAR, 
	module VARCHAR, 
	title VARCHAR, 
	description TEXT, 
	status VARCHAR, 
	source_type VARCHAR, 
	related_entity_type VARCHAR, 
	related_entity_id INTEGER, 
	suggested_action TEXT, 
	created_task_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	resolved_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (warning_code), 
	FOREIGN KEY(created_task_id) REFERENCES work_tasks (id)
);
CREATE INDEX ix_risk_warnings_status_severity ON risk_warnings (status, severity);


CREATE TABLE search_events (
	id INTEGER NOT NULL, 
	keyword VARCHAR, 
	normalized_keyword VARCHAR, 
	reader_id INTEGER, 
	session_id INTEGER, 
	result_count INTEGER, 
	clicked_book_id INTEGER, 
	source_app VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reader_id) REFERENCES reader_accounts (id), 
	FOREIGN KEY(clicked_book_id) REFERENCES books (id)
);


CREATE TABLE shelf_positions (
	id INTEGER NOT NULL, 
	position_code VARCHAR, 
	shelf_id INTEGER, 
	layer_no INTEGER, 
	side VARCHAR, 
	capacity_estimate INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (position_code), 
	FOREIGN KEY(shelf_id) REFERENCES shelves (id)
);


CREATE TABLE shelves (
	id INTEGER NOT NULL, 
	shelf_code VARCHAR, 
	zone_id INTEGER, 
	zone_code VARCHAR, 
	floor VARCHAR, 
	shelf_index INTEGER, 
	layer_count INTEGER, 
	side_rule VARCHAR, 
	shelf_type VARCHAR, 
	counted_in_72_formal_shelves BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (shelf_code), 
	FOREIGN KEY(zone_id) REFERENCES library_zones (id)
);


CREATE TABLE system_settings (
	id INTEGER NOT NULL, 
	setting_key VARCHAR, 
	setting_value VARCHAR, 
	value_type VARCHAR, 
	scope VARCHAR, 
	description TEXT, 
	is_active BOOLEAN, 
	updated_by_admin_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (setting_key), 
	FOREIGN KEY(updated_by_admin_id) REFERENCES admin_users (id)
);


CREATE TABLE work_task_events (
	id INTEGER NOT NULL, 
	task_id INTEGER, 
	event_type VARCHAR, 
	actor_type VARCHAR, 
	actor_admin_id INTEGER, 
	actor_agent_run_id INTEGER, 
	detail_json TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(task_id) REFERENCES work_tasks (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(actor_agent_run_id) REFERENCES agent_runs (id)
);


CREATE TABLE work_tasks (
	id INTEGER NOT NULL, 
	source_task_id INTEGER, 
	task_code VARCHAR, 
	title VARCHAR, 
	description TEXT, 
	task_type VARCHAR, 
	task_group VARCHAR, 
	priority VARCHAR, 
	status VARCHAR, 
	source_type VARCHAR, 
	ai_default_executor BOOLEAN, 
	assigned_to_admin_id INTEGER, 
	claimed_by_admin_id INTEGER, 
	claimed_by_code VARCHAR, 
	resolved_by_admin_id INTEGER, 
	resolved_by_code VARCHAR, 
	related_entity_type VARCHAR, 
	related_entity_id VARCHAR, 
	sla_due_at DATETIME, 
	claimed_at DATETIME, 
	resolved_at DATETIME, 
	cancelled_at DATETIME, 
	resolution VARCHAR, 
	requires_human_confirmation BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	handler_type VARCHAR, 
	claim_status VARCHAR, 
	ai_run_id INTEGER, 
	ai_started_at DATETIME, 
	ai_finished_at DATETIME, 
	ai_error VARCHAR, 
	ai_confidence FLOAT, 
	ai_result VARCHAR, 
	takeover_by_admin_id INTEGER, 
	takeover_by_code VARCHAR, 
	takeover_at DATETIME, 
	takeover_reason VARCHAR, 
	last_actor_type VARCHAR, 
	last_actor_id VARCHAR, 
	last_transition VARCHAR, 
	last_transition_at DATETIME, 
	risk_warning_code VARCHAR, 
	queue_name VARCHAR, 
	priority_score INTEGER, 
	risk_level VARCHAR, 
	urgency_reason TEXT, 
	source_payload_json TEXT, 
	execution_context_json TEXT, 
	ai_plan_json TEXT, 
	ai_trace_json TEXT, 
	lease_owner VARCHAR, 
	lease_expires_at DATETIME, 
	attempt_count INTEGER, 
	max_attempts INTEGER, 
	next_attempt_at DATETIME, 
	interrupted_at DATETIME, 
	interrupt_reason TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_work_tasks_status CHECK (status IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing', 'resolved', 'cancelled')), 
	UNIQUE (task_code), 
	FOREIGN KEY(assigned_to_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(claimed_by_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(resolved_by_admin_id) REFERENCES admin_users (id), 
	FOREIGN KEY(takeover_by_admin_id) REFERENCES admin_users (id)
);
CREATE INDEX ix_work_tasks_claimed_status ON work_tasks (claimed_by_admin_id, status);
CREATE INDEX ix_work_tasks_priority_score ON work_tasks (status, priority_score);
CREATE INDEX ix_work_tasks_queue_lease ON work_tasks (queue_name, status, lease_expires_at);
CREATE INDEX ix_work_tasks_status_group ON work_tasks (status, task_group);

CREATE TABLE ai_task_checkpoints (
	id INTEGER NOT NULL, 
	checkpoint_code VARCHAR, 
	task_id INTEGER, 
	run_id INTEGER, 
	worker_id VARCHAR, 
	node_name VARCHAR, 
	status VARCHAR, 
	state_json TEXT, 
	resume_token VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (checkpoint_code), 
	FOREIGN KEY(task_id) REFERENCES work_tasks (id), 
	FOREIGN KEY(run_id) REFERENCES agent_runs (id)
);
CREATE INDEX ix_ai_task_checkpoints_task_run ON ai_task_checkpoints (task_id, run_id, status);

DROP VIEW IF EXISTS v_book_availability;
CREATE VIEW v_book_availability AS
SELECT
    b.id AS book_id,
    b.book_code,
    b.title,
    b.category_code,
    b.category_name,
    COUNT(c.id) AS total_copies,
    SUM(CASE WHEN c.copy_status = 'available' THEN 1 ELSE 0 END) AS available_copies,
    SUM(CASE WHEN c.copy_status = 'borrowed' THEN 1 ELSE 0 END) AS borrowed_copies,
    SUM(CASE WHEN c.copy_status = 'reserved' THEN 1 ELSE 0 END) AS reserved_copies,
    SUM(CASE WHEN c.copy_status IN ('maintenance', 'unavailable') THEN 1 ELSE 0 END) AS maintenance_copies,
    SUM(CASE WHEN c.copy_status = 'lost' THEN 1 ELSE 0 END) AS lost_copies
FROM books b
LEFT JOIN book_copies c ON c.book_id = b.id
GROUP BY b.id, b.book_code, b.title, b.category_code, b.category_name;

DROP VIEW IF EXISTS v_reader_borrow_summary;
CREATE VIEW v_reader_borrow_summary AS
SELECT
    r.id AS reader_id,
    r.reader_code,
    r.name,
    r.status,
    COUNT(DISTINCT CASE WHEN l.status IN ('active', 'borrowed') THEN l.id END) AS active_loans,
    COUNT(DISTINCT CASE WHEN l.status = 'overdue' THEN l.id END) AS overdue_loans,
    COUNT(DISTINCT CASE WHEN l.status = 'returned' THEN l.id END) AS returned_loans,
    COUNT(DISTINCT CASE WHEN rv.status IN ('waiting', 'ready_for_pickup') THEN rv.id END) AS active_reservations,
    MAX(l.borrowed_at) AS last_borrowed_at
FROM reader_accounts r
LEFT JOIN loans l ON l.reader_id = r.id
LEFT JOIN reservations rv ON rv.reader_id = r.id
GROUP BY r.id, r.reader_code, r.name, r.status;

DROP VIEW IF EXISTS v_admin_home_kpis;
CREATE VIEW v_admin_home_kpis AS
SELECT 'book_titles' AS metric_key, COUNT(*) AS metric_value FROM books
UNION ALL
SELECT 'book_copies' AS metric_key, COUNT(*) AS metric_value FROM book_copies
UNION ALL
SELECT 'readers' AS metric_key, COUNT(*) AS metric_value FROM reader_accounts
UNION ALL
SELECT 'active_loans' AS metric_key, COUNT(*) AS metric_value FROM loans WHERE status IN ('active', 'borrowed', 'overdue')
UNION ALL
SELECT 'pending_reservations' AS metric_key, COUNT(*) AS metric_value FROM reservations WHERE status IN ('waiting', 'ready_for_pickup')
UNION ALL
SELECT 'open_tasks' AS metric_key, COUNT(*) AS metric_value FROM work_tasks WHERE status IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing')
UNION ALL
SELECT 'open_risks' AS metric_key, COUNT(*) AS metric_value FROM risk_warnings WHERE status IN ('active', 'open', 'reviewing');

DROP VIEW IF EXISTS v_collection_health_by_zone;
CREATE VIEW v_collection_health_by_zone AS
SELECT
    z.id AS zone_id,
    z.zone_code,
    z.zone_name,
    COUNT(c.id) AS copy_count,
    SUM(CASE WHEN c.copy_status = 'available' THEN 1 ELSE 0 END) AS available_count,
    SUM(CASE WHEN c.copy_status = 'borrowed' THEN 1 ELSE 0 END) AS borrowed_count,
    SUM(CASE WHEN c.copy_status IN ('maintenance', 'unavailable', 'lost', 'withdrawn') THEN 1 ELSE 0 END) AS unavailable_count
FROM library_zones z
LEFT JOIN book_copies c ON c.current_zone_id = z.id
GROUP BY z.id, z.zone_code, z.zone_name;

DROP VIEW IF EXISTS v_task_pool;
CREATE VIEW v_task_pool AS
SELECT
    t.id,
    t.task_code,
    t.title,
    t.task_type,
    t.task_group,
    t.priority,
    t.priority_score,
    t.risk_level,
    t.queue_name,
    t.status,
    t.handler_type,
    t.claim_status,
    t.lease_owner,
    t.lease_expires_at,
    t.attempt_count,
    t.max_attempts,
    t.interrupted_at,
    t.interrupt_reason,
    t.ai_default_executor,
    t.assigned_to_admin_id,
    t.claimed_by_admin_id,
    t.related_entity_type,
    t.related_entity_id,
    t.sla_due_at,
    t.created_at,
    t.updated_at
FROM work_tasks t;

DROP VIEW IF EXISTS v_notification_summary;
CREATE VIEW v_notification_summary AS
SELECT
    channel,
    notification_type,
    status,
    COUNT(*) AS notification_count,
    MIN(created_at) AS first_created_at,
    MAX(created_at) AS last_created_at
FROM notifications
GROUP BY channel, notification_type, status;

DROP VIEW IF EXISTS v_superadmin_governance_overview;
CREATE VIEW v_superadmin_governance_overview AS
SELECT 'admins' AS metric_key, COUNT(*) AS metric_value FROM admin_users
UNION ALL
SELECT 'super_admins' AS metric_key, COUNT(*) AS metric_value FROM admin_users WHERE is_super_admin = 1
UNION ALL
SELECT 'enabled_ai_rules' AS metric_key, COUNT(*) AS metric_value FROM ai_rules WHERE is_enabled = 1 AND status = 'active'
UNION ALL
SELECT 'pending_ai_approvals' AS metric_key, COUNT(*) AS metric_value FROM ai_approval_requests WHERE status = 'pending'
UNION ALL
SELECT 'open_risk_warnings' AS metric_key, COUNT(*) AS metric_value FROM risk_warnings WHERE status IN ('active', 'open', 'reviewing')
UNION ALL
SELECT 'audit_events' AS metric_key, COUNT(*) AS metric_value FROM audit_events;

DROP VIEW IF EXISTS v_ai_rule_runtime_status;
CREATE VIEW v_ai_rule_runtime_status AS
SELECT
    r.id AS rule_id,
    r.rule_code,
    r.rule_name,
    r.module,
    r.status,
    r.is_enabled,
    r.current_version_id,
    COUNT(l.id) AS execution_count,
    MAX(l.created_at) AS last_executed_at
FROM ai_rules r
LEFT JOIN ai_rule_execution_logs l ON l.rule_id = r.id
GROUP BY r.id, r.rule_code, r.rule_name, r.module, r.status, r.is_enabled, r.current_version_id;

DROP VIEW IF EXISTS v_audit_risk_distribution;
CREATE VIEW v_audit_risk_distribution AS
SELECT
    'audit' AS distribution_type,
    action AS bucket,
    result AS sub_bucket,
    COUNT(*) AS event_count
FROM audit_events
GROUP BY action, result
UNION ALL
SELECT
    'risk' AS distribution_type,
    warning_type AS bucket,
    severity AS sub_bucket,
    COUNT(*) AS event_count
FROM risk_warnings
GROUP BY warning_type, severity;
