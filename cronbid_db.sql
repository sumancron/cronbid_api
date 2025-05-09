-- This SQL script creates the necessary tables for the CronBid application.
-- Table: cronbid_users
CREATE TABLE cronbid_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(255),
    tax_id VARCHAR(100),
    email VARCHAR(255) NOT NULL,
    additional_email VARCHAR(255),
    address TEXT,
    country VARCHAR(100),
    phone VARCHAR(20),
    skype VARCHAR(100),
    referrer_email VARCHAR(255),
    password VARCHAR(255) NOT NULL,
    is_company BOOLEAN DEFAULT FALSE,
    terms_accepted BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Table: cronbid_campaigns

CREATE TABLE cronbid_campaigns (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id VARCHAR(255) NOT NULL,
    brand VARCHAR(255) DEFAULT NULL,
    app_package_id TEXT DEFAULT NULL,
    app_name VARCHAR(255) DEFAULT NULL,
    preview_url TEXT DEFAULT NULL,
    description TEXT DEFAULT NULL,
    category VARCHAR(255) DEFAULT NULL,
    campaign_title VARCHAR(255) DEFAULT NULL,
    kpis TEXT DEFAULT NULL,
    mmp TEXT DEFAULT NULL,
    click_url TEXT DEFAULT NULL,
    impression_url TEXT DEFAULT NULL,
    deeplink TEXT DEFAULT NULL,
    creatives TEXT DEFAULT NULL,
    events TEXT DEFAULT NULL,
    payable TINYINT(1) DEFAULT 0,
    event_amount DECIMAL(12,2) DEFAULT NULL,
    campaign_budget DECIMAL(15,2) DEFAULT NULL,
    daily_budget DECIMAL(15,2) DEFAULT NULL,
    monthly_budget DECIMAL(15,2) DEFAULT NULL,
    country VARCHAR(255) DEFAULT NULL,
    included_states TEXT DEFAULT NULL,
    excluded_states TEXT DEFAULT NULL,
    programmatic TINYINT(1) DEFAULT 0,
    core_partners TEXT DEFAULT NULL,
    direct_apps TEXT DEFAULT NULL,
    oems TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT NULL,
    log_id VARCHAR(100) DEFAULT NULL,
    status ENUM('active','inactive', 'paused', 'ended') DEFAULT 'active',
    PRIMARY KEY (id),
    UNIQUE KEY (campaign_id),
    INDEX idx_app_package_id (app_package_id(191)),  -- Prefix index to avoid exceeding key length limit
    INDEX idx_country (country),
    INDEX idx_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



-- Table: cronbid_brands

CREATE TABLE cronbid_brands (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    brand_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) DEFAULT NULL,
    brand_logo TEXT DEFAULT NULL,
    country VARCHAR(255) DEFAULT NULL,
    state_region VARCHAR(255) DEFAULT NULL,
    city VARCHAR(255) DEFAULT NULL,
    address_line_1 TEXT DEFAULT NULL,
    address_line_2 TEXT DEFAULT NULL,
    zip_postal_code VARCHAR(20) DEFAULT NULL,
    currency VARCHAR(100) DEFAULT NULL,
    first_name VARCHAR(255) DEFAULT NULL,
    last_name VARCHAR(255) DEFAULT NULL,
    contact VARCHAR(255) DEFAULT NULL,
    mobile VARCHAR(20) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT NULL,
    log_id VARCHAR(100) DEFAULT NULL,
    status ENUM('active','inactive') DEFAULT 'active',
    PRIMARY KEY (id),
    UNIQUE KEY (brand_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Table: cronbid_campaigns_logs

CREATE TABLE cronbid_logs (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_id VARCHAR(255) NOT NULL,  -- Unique log ID to associate with actions
    action ENUM('create', 'update', 'delete', 'view') NOT NULL,  -- Type of action performed
    table_name VARCHAR(255) NOT NULL,  -- Table in which the action was performed (e.g., cronbid_campaigns, cronbid_brands)
    record_id  TEXT NOT NULL,  -- ID of the record affected by the action
    user_id TEXT NOT NULL,  -- ID of the user who performed the action
    username VARCHAR(255) DEFAULT NULL,  -- Optional: Username of the user
    action_description TEXT DEFAULT NULL,  -- Optional: A description of the action (e.g., reason for the change)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- When the action occurred
    PRIMARY KEY (id),
    UNIQUE KEY (log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: cronbid_user_funds

CREATE TABLE cronbid_user_funds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fund_id VARCHAR(150),
    user_id VARCHAR(150),
    user_name VARCHAR(255),
    fund DECIMAL(10,2),
    currency VARCHAR(10) DEFAULT 'USD',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Table: cronbid_fund_transactions
CREATE TABLE cronbid_fund_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(150),
    user_id VARCHAR(150),
    user_name VARCHAR(255),
    currency VARCHAR(10) DEFAULT 'USD',
    amount DECIMAL(10,2),
    type ENUM('credit', 'debit'),
    description TEXT,
    balance_after_transaction DECIMAL(10,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);




-- Inserting data into cronbid_campaigns
INSERT INTO cronbid_campaigns (
    campaign_id, brand, app_package_id, app_name, preview_url, description,
    category, campaign_title, kpis, mmp, click_url, impression_url, deeplink,
    creatives, events, payable, event_amount, campaign_budget, daily_budget,
    monthly_budget, country, included_states, excluded_states, programmatic,
    core_partners, direct_apps, oems, created_by, log_id, status
) VALUES
    ('campaign001', 'Brand A', 'com.app.a', 'App A', 'http://preview.com/a', 'Description of Campaign A',
     'Category A', 'Campaign A Title', 'KPIs A', 'MMP A', 'http://click.com/a', 'http://impression.com/a', 'http://deeplink.com/a',
     'Creative A', 'Event A', 1, 500.00, 1000.00, 100.00, 3000.00, 'USA', 'California, Texas', 'New York', 1,
     'Partner A, Partner B', 'App1, App2', 'OEM A', 'user123', 'log001', 'active');

-- Inserting data into cronbid_brands
INSERT INTO cronbid_brands (
    brand_id, company_name, brand_logo, country, state_region, city, address_line_1, address_line_2, zip_postal_code,
    currency, first_name, last_name, contact, mobile, created_by, log_id, status
) VALUES
    ('brand001', 'Brand A Company', 'http://logo.com/a', 'USA', 'California', 'Los Angeles', '123 Main St', 'Suite 4', '90001',
     'USD', 'John', 'Doe', 'john.doe@example.com', '+1234567890', 'user123', 'log001', 'active'),
    ('brand002', 'Brand B Company', 'http://logo.com/b', 'USA', 'Texas', 'Houston', '456 Elm St', 'Apt 9', '77001',
     'USD', 'Jane', 'Smith', 'jane.smith@example.com', '+0987654321', 'user123', 'log002', 'active');

-- Inserting data into cronbid_campaigns_logs
INSERT INTO cronbid_logs (
    log_id, action, table_name, record_id, user_id, username, action_description, created_at
) VALUES
    ('log001', 'create', 'cronbid_campaigns', '1', 'user123', 'john_doe', 'Created Campaign A', CURRENT_TIMESTAMP),
    ('log002', 'update', 'cronbid_campaigns', '1', 'user123', 'john_doe', 'Updated Campaign A', CURRENT_TIMESTAMP),
    ('log003', 'delete', 'cronbid_campaigns', '2', 'user123', 'john_doe', 'Deleted Campaign B', CURRENT_TIMESTAMP);
