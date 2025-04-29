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
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fund_id varchar(255) NOT NULL,
    user_id TEXT NOT NULL,  -- Reference to the user
    total_funds DECIMAL(15,2) DEFAULT 0.00,  -- Total funds added to the user's account
    funds_added DECIMAL(15,2) DEFAULT 0.00,  -- Funds added during the current transaction
    funds_used DECIMAL(15,2) DEFAULT 0.00,   -- Funds already used from the account
    remaining_funds DECIMAL(15,2) DEFAULT 0.00,  -- Remaining funds available
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- Timestamp of when the fund entry was created
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- Timestamp of the last update
    created_by VARCHAR(100) DEFAULT NULL,
    log_id VARCHAR(100) DEFAULT NULL,
    status ENUM('active','inactive') DEFAULT 'active',
    PRIMARY KEY (id),
    UNIQUE KEY (fund_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Table: cronbid_brand_budgets

CREATE TABLE cronbid_brand_budgets (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    budget_id TEXT NOT NULL,
    user_id TEXT NOT NULL,  -- Reference to the user who allocated the budget
    brand_id VARCHAR(255) NOT NULL,  -- Reference to the brand
    allocated_budget DECIMAL(15,2) DEFAULT 0.00,  -- Total budget allocated to the brand
    daily_budget DECIMAL(15,2) DEFAULT 0.00,      -- Daily budget for the brand
    monthly_budget DECIMAL(15,2) DEFAULT 0.00,    -- Monthly budget for the brand
    remaining_budget DECIMAL(15,2) DEFAULT 0.00,   -- Remaining budget allocated to the brand
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- Timestamp when the budget was allocated
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- Last updated timestamp
    PRIMARY KEY (id),
    UNIQUE KEY (budget_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
