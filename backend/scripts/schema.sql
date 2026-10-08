-- ============================================================================
-- 电商运营助手 · 数据库结构（SQLite）
-- ============================================================================
-- 本文件由 backend/scripts/export_schema.py 从 SQLAlchemy 模型自动导出，
-- 模型（backend/app/models/）是唯一事实来源，请勿手工修改本文件后直接使用；
-- 如需调整表结构，请修改模型后重新执行：
--
--     cd backend && ../.venv/Scripts/python.exe scripts/export_schema.py
--
-- 应用启动时会自动建表（Base.metadata.create_all），本文件用于：
--   1) 课程验收时直接查看表结构
--   2) 在其它工具或环境中手工建库
--
-- 生成时间：2026-10-08 15:36:37
-- 表数量：24
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 表清单：
--    1. ad_experiments
--    2. ad_recommendations
--    3. competitor_monitor_snapshots
--    4. competitor_monitors
--    5. competitors
--    6. creative_plans
--    7. generated_assets
--    8. generation_job_events
--    9. generation_jobs
--   10. inventory_items
--   11. inventory_movements
--   12. performance_records
--   13. platform_accounts
--   14. platform_product_mappings
--   15. product_diagnoses
--   16. product_skus
--   17. products
--   18. promotion_link_clicks
--   19. promotion_links
--   20. public_link_parse_tasks
--   21. review_reports
--   22. stores
--   23. system_settings
--   24. users

CREATE TABLE stores (
	store_name VARCHAR(128) NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	external_store_id VARCHAR(128) NOT NULL, 
	owner_name VARCHAR(64) NOT NULL, 
	remark TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE system_settings (
	"key" VARCHAR(64) NOT NULL, 
	value TEXT NOT NULL, 
	value_type VARCHAR(16) NOT NULL, 
	category VARCHAR(32) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	editable INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_system_settings_key ON system_settings ("key");

CREATE TABLE users (
	username VARCHAR(64) NOT NULL, 
	display_name VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	last_login_at DATETIME, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE platform_accounts (
	store_id INTEGER NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	account_name VARCHAR(128) NOT NULL, 
	auth_status VARCHAR(32) NOT NULL, 
	auth_meta_json JSON, 
	remark TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE
);
CREATE INDEX ix_platform_accounts_store_id ON platform_accounts (store_id);

CREATE TABLE products (
	store_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	category VARCHAR(128) NOT NULL, 
	price FLOAT NOT NULL, 
	cost FLOAT NOT NULL, 
	target_audience TEXT NOT NULL, 
	selling_points TEXT NOT NULL, 
	product_url VARCHAR(512) NOT NULL, 
	images_json JSON, 
	status VARCHAR(16) NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE
);
CREATE INDEX ix_products_store_id ON products (store_id);

CREATE TABLE ad_recommendations (
	product_id INTEGER NOT NULL, 
	summary_text TEXT NOT NULL, 
	objective_text TEXT NOT NULL, 
	audience_segments_json JSON, 
	budget_plan_json JSON, 
	creative_tests_json JSON, 
	bid_strategy_json JSON, 
	risk_controls_json JSON, 
	next_steps_json JSON, 
	confirm_status VARCHAR(16) NOT NULL, 
	confirmed_by INTEGER, 
	confirmed_at DATETIME, 
	confirm_remark TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_ad_recommendations_product_id ON ad_recommendations (product_id);

CREATE TABLE competitors (
	product_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	url VARCHAR(512) NOT NULL, 
	price FLOAT NOT NULL, 
	sales_hint VARCHAR(128) NOT NULL, 
	title VARCHAR(512) NOT NULL, 
	main_image VARCHAR(512) NOT NULL, 
	selling_points TEXT NOT NULL, 
	review_keywords TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_competitors_product_id ON competitors (product_id);

CREATE TABLE creative_plans (
	product_id INTEGER NOT NULL, 
	plan_type VARCHAR(32) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	content_json JSON, 
	rationale_text TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_creative_plans_product_id ON creative_plans (product_id);

CREATE TABLE platform_product_mappings (
	product_id INTEGER NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	platform_product_id VARCHAR(128) NOT NULL, 
	platform_sku_id VARCHAR(128) NOT NULL, 
	mapping_status VARCHAR(32) NOT NULL, 
	raw_payload_json JSON, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_platform_product_mappings_product_id ON platform_product_mappings (product_id);

CREATE TABLE product_diagnoses (
	product_id INTEGER NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	summary_text TEXT NOT NULL, 
	positioning TEXT NOT NULL, 
	price_band TEXT NOT NULL, 
	audience_insights TEXT NOT NULL, 
	pain_points TEXT NOT NULL, 
	selling_point_analysis TEXT NOT NULL, 
	risks TEXT NOT NULL, 
	recommendations TEXT NOT NULL, 
	raw_output JSON, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_product_diagnoses_product_id ON product_diagnoses (product_id);

CREATE TABLE product_skus (
	product_id INTEGER NOT NULL, 
	sku_code VARCHAR(128) NOT NULL, 
	sku_name VARCHAR(255) NOT NULL, 
	spec_json JSON, 
	price FLOAT NOT NULL, 
	cost FLOAT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	platform_sku_id VARCHAR(128) NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_product_skus_product_id ON product_skus (product_id);

CREATE TABLE promotion_links (
	product_id INTEGER NOT NULL, 
	link_name VARCHAR(255) NOT NULL, 
	target_url VARCHAR(512) NOT NULL, 
	tracking_code VARCHAR(64) NOT NULL, 
	utm_json JSON, 
	status VARCHAR(16) NOT NULL, 
	click_count INTEGER NOT NULL, 
	scene_text TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_promotion_links_product_id ON promotion_links (product_id);
CREATE UNIQUE INDEX ix_promotion_links_tracking_code ON promotion_links (tracking_code);

CREATE TABLE public_link_parse_tasks (
	product_id INTEGER NOT NULL, 
	source_url VARCHAR(512) NOT NULL, 
	task_status VARCHAR(32) NOT NULL, 
	attempts INTEGER NOT NULL, 
	result_json JSON, 
	error_message TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_public_link_parse_tasks_product_id ON public_link_parse_tasks (product_id);

CREATE TABLE review_reports (
	product_id INTEGER NOT NULL, 
	period_start DATE, 
	period_end DATE, 
	summary_text TEXT NOT NULL, 
	insights_json JSON, 
	next_actions_json JSON, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_review_reports_product_id ON review_reports (product_id);

CREATE TABLE competitor_monitors (
	competitor_id INTEGER NOT NULL, 
	monitor_status VARCHAR(32) NOT NULL, 
	interval_minutes INTEGER NOT NULL, 
	next_run_at DATETIME, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(competitor_id) REFERENCES competitors (id) ON DELETE CASCADE
);
CREATE INDEX ix_competitor_monitors_competitor_id ON competitor_monitors (competitor_id);
CREATE INDEX ix_competitor_monitors_next_run_at ON competitor_monitors (next_run_at);

CREATE TABLE generated_assets (
	product_id INTEGER NOT NULL, 
	creative_plan_id INTEGER, 
	asset_type VARCHAR(16) NOT NULL, 
	asset_url VARCHAR(512) NOT NULL, 
	file_path VARCHAR(512) NOT NULL, 
	model_name VARCHAR(64) NOT NULL, 
	width INTEGER NOT NULL, 
	height INTEGER NOT NULL, 
	duration_sec FLOAT, 
	review_status VARCHAR(16) NOT NULL, 
	version_no INTEGER NOT NULL, 
	usage_scene VARCHAR(64) NOT NULL, 
	score FLOAT, 
	tags_json JSON, 
	remark TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id) ON DELETE SET NULL
);
CREATE INDEX ix_generated_assets_creative_plan_id ON generated_assets (creative_plan_id);
CREATE INDEX ix_generated_assets_product_id ON generated_assets (product_id);

CREATE TABLE generation_jobs (
	product_id INTEGER NOT NULL, 
	creative_plan_id INTEGER, 
	job_kind VARCHAR(16) NOT NULL, 
	job_status VARCHAR(16) NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	locked_at DATETIME, 
	locked_by VARCHAR(64) NOT NULL, 
	next_run_at DATETIME, 
	params_json JSON, 
	result_json JSON, 
	error_message TEXT NOT NULL, 
	started_at DATETIME, 
	finished_at DATETIME, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id) ON DELETE SET NULL
);
CREATE INDEX ix_generation_jobs_creative_plan_id ON generation_jobs (creative_plan_id);
CREATE INDEX ix_generation_jobs_job_status ON generation_jobs (job_status);
CREATE INDEX ix_generation_jobs_next_run_at ON generation_jobs (next_run_at);
CREATE INDEX ix_generation_jobs_product_id ON generation_jobs (product_id);

CREATE TABLE inventory_items (
	sku_id INTEGER NOT NULL, 
	stock_qty INTEGER NOT NULL, 
	locked_qty INTEGER NOT NULL, 
	warning_threshold INTEGER NOT NULL, 
	location_text VARCHAR(128) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sku_id) REFERENCES product_skus (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_inventory_items_sku_id ON inventory_items (sku_id);

CREATE TABLE inventory_movements (
	sku_id INTEGER NOT NULL, 
	movement_type VARCHAR(32) NOT NULL, 
	change_qty INTEGER NOT NULL, 
	before_qty INTEGER NOT NULL, 
	after_qty INTEGER NOT NULL, 
	reason_text TEXT NOT NULL, 
	reference_type VARCHAR(32) NOT NULL, 
	reference_id INTEGER, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sku_id) REFERENCES product_skus (id) ON DELETE CASCADE
);
CREATE INDEX ix_inventory_movements_sku_id ON inventory_movements (sku_id);

CREATE TABLE promotion_link_clicks (
	promotion_link_id INTEGER NOT NULL, 
	clicked_at DATETIME NOT NULL, 
	client_ip VARCHAR(64) NOT NULL, 
	user_agent VARCHAR(512) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(promotion_link_id) REFERENCES promotion_links (id) ON DELETE CASCADE
);
CREATE INDEX ix_promotion_link_clicks_promotion_link_id ON promotion_link_clicks (promotion_link_id);

CREATE TABLE ad_experiments (
	product_id INTEGER NOT NULL, 
	related_asset_id INTEGER, 
	related_link_id INTEGER, 
	experiment_name VARCHAR(255) NOT NULL, 
	target_text TEXT NOT NULL, 
	audience_text TEXT NOT NULL, 
	budget_amount FLOAT NOT NULL, 
	success_metric_text TEXT NOT NULL, 
	hypothesis_text TEXT NOT NULL, 
	experiment_status VARCHAR(16) NOT NULL, 
	id INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(related_asset_id) REFERENCES generated_assets (id) ON DELETE SET NULL, 
	FOREIGN KEY(related_link_id) REFERENCES promotion_links (id) ON DELETE SET NULL
);
CREATE INDEX ix_ad_experiments_product_id ON ad_experiments (product_id);

CREATE TABLE competitor_monitor_snapshots (
	monitor_id INTEGER NOT NULL, 
	price FLOAT NOT NULL, 
	sales_hint VARCHAR(128) NOT NULL, 
	selling_points TEXT NOT NULL, 
	raw_payload_json JSON, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(monitor_id) REFERENCES competitor_monitors (id) ON DELETE CASCADE
);
CREATE INDEX ix_competitor_monitor_snapshots_monitor_id ON competitor_monitor_snapshots (monitor_id);

CREATE TABLE generation_job_events (
	job_id INTEGER NOT NULL, 
	event_type VARCHAR(32) NOT NULL, 
	event_message TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES generation_jobs (id) ON DELETE CASCADE
);
CREATE INDEX ix_generation_job_events_job_id ON generation_job_events (job_id);

CREATE TABLE performance_records (
	product_id INTEGER NOT NULL, 
	creative_plan_id INTEGER, 
	generated_asset_id INTEGER, 
	promotion_link_id INTEGER, 
	experiment_id INTEGER, 
	period_start DATE, 
	period_end DATE, 
	impressions INTEGER NOT NULL, 
	clicks INTEGER NOT NULL, 
	ctr FLOAT NOT NULL, 
	conversions INTEGER NOT NULL, 
	conversion_rate FLOAT NOT NULL, 
	spend FLOAT NOT NULL, 
	revenue FLOAT NOT NULL, 
	roi FLOAT NOT NULL, 
	notes TEXT NOT NULL, 
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id) ON DELETE SET NULL, 
	FOREIGN KEY(generated_asset_id) REFERENCES generated_assets (id) ON DELETE SET NULL, 
	FOREIGN KEY(promotion_link_id) REFERENCES promotion_links (id) ON DELETE SET NULL, 
	FOREIGN KEY(experiment_id) REFERENCES ad_experiments (id) ON DELETE SET NULL
);
CREATE INDEX ix_performance_records_product_id ON performance_records (product_id);


-- ============================================================================
-- 种子数据（演示账号 + 系统默认参数）
-- ============================================================================
-- 说明：密码使用 PBKDF2-SHA256（10 万次迭代）哈希，盐值随机，
-- 因此下方不提供固定哈希值；请通过应用启动自动写入，或执行：
--
--     cd backend && ../.venv/Scripts/python.exe scripts/init_db.py
--
-- 默认演示账号：
--   admin    / admin123      管理员
--   operator / operator123   运营人员
--   viewer   / viewer123     查看人员
--
-- 一键生成完整演示数据（店铺、商品、竞品、方案、素材、投放、经营数据、复盘）：
--   POST /api/v1/workspace/demo-data   （需 admin 登录）
-- ============================================================================
