-- ============================================
-- 0. ENUM TYPE FOR GOAL
-- ============================================
CREATE TYPE user_goal AS ENUM ('weight_loss', 'weight_maintenance', 'weight_gain');

-- ============================================
-- 1. USERS
-- ============================================
CREATE TABLE users (
    username VARCHAR(255) NOT NULL PRIMARY KEY,
    hash_password VARCHAR(255) NOT NULL,
    age INT NOT NULL,
    bmr DECIMAL(6,4) NOT NULL,
    gender VARCHAR(5) CHECK (gender IN ('w', 'm', 'None')),
    goal user_goal DEFAULT 'weight_maintenance',
    height DECIMAL(5,1) NOT NULL CHECK (height BETWEEN 50 AND 250),
    weight DECIMAL(5,1) NOT NULL CHECK (weight BETWEEN 20 AND 500),
    norm_calories DECIMAL(6,1) NOT NULL CHECK (norm_calories BETWEEN 400 AND 10000),
    norm_proteins DECIMAL(6,1) NOT NULL CHECK (norm_proteins BETWEEN 0 AND 1000),
    norm_fats DECIMAL(6,1) NOT NULL CHECK (norm_fats BETWEEN 0 AND 1000),
    norm_carbohydrates DECIMAL(6,1) NOT NULL CHECK (norm_carbohydrates BETWEEN 0 AND 1000)
);

-- ============================================
-- 2. USER METRICS HISTORY
-- ============================================
CREATE TABLE user_metrics_history (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    age INT NOT NULL,
    bmr DECIMAL(6,4) NOT NULL,
    gender VARCHAR(5) CHECK (gender IN ('w', 'm', 'None')),
    goal user_goal DEFAULT 'weight_maintenance',
    height DECIMAL(5,1) NOT NULL CHECK (height BETWEEN 50 AND 250),
    weight DECIMAL(5,1) NOT NULL CHECK (weight BETWEEN 20 AND 500),
    norm_calories DECIMAL(6,1) NOT NULL CHECK (norm_calories BETWEEN 400 AND 10000),
    norm_proteins DECIMAL(6,1) NOT NULL CHECK (norm_proteins BETWEEN 0 AND 1000),
    norm_fats DECIMAL(6,1) NOT NULL CHECK (norm_fats BETWEEN 0 AND 1000),
    norm_carbohydrates DECIMAL(6,1) NOT NULL CHECK (norm_carbohydrates BETWEEN 0 AND 1000),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);

CREATE INDEX idx_metrics_username ON user_metrics_history(username);
CREATE INDEX idx_metrics_username_date ON user_metrics_history(username, recorded_at);

-- ============================================
-- 3. DAY
-- ============================================
CREATE TABLE day (
    id SERIAL NOT NULL PRIMARY KEY,
    record_date DATE NOT NULL,
    username VARCHAR(255) NOT NULL,
    total_calories DECIMAL(6,1) DEFAULT 0,
    total_proteins DECIMAL(6,1) DEFAULT 0,
    total_fats DECIMAL(6,1) DEFAULT 0,
    total_carbohydrates DECIMAL(6,1) DEFAULT 0,
    UNIQUE (record_date, username),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);

CREATE INDEX idx_day_users_date ON day(username, record_date);

-- ============================================
-- 4. INGREDIENT
-- ============================================
CREATE TABLE ingredient (
    id SERIAL NOT NULL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    calories DECIMAL(6,1) DEFAULT 0,
    proteins DECIMAL(6,1) DEFAULT 0,
    fats DECIMAL(6,1) DEFAULT 0,
    carbohydrates DECIMAL(6,1) DEFAULT 0
);

-- ============================================
-- 5. LIST INGREDIENTS
-- ============================================
CREATE TABLE list_ingredients (
    id SERIAL NOT NULL PRIMARY KEY,
    id_day INT NOT NULL,
    id_ingredient INT NOT NULL,
    weight DECIMAL(6,1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_day) REFERENCES day(id) ON DELETE CASCADE,
    FOREIGN KEY (id_ingredient) REFERENCES ingredient(id),
    UNIQUE (id_day, id_ingredient)
);

CREATE INDEX idx_list_ingredients_id_day ON list_ingredients(id_day);

-- ============================================
-- 6. TRIGGER: Recalculate day totals
-- ============================================

CREATE OR REPLACE FUNCTION recalculate_day_totals()
RETURNS TRIGGER AS $$
DECLARE
    v_day_ids INT[];
    v_day_id INT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_day_ids := ARRAY[NEW.id_day];
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.id_day = NEW.id_day THEN
            v_day_ids := ARRAY[NEW.id_day];
        ELSE
            v_day_ids := ARRAY[OLD.id_day, NEW.id_day];
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_day_ids := ARRAY[OLD.id_day];
    END IF;

    FOREACH v_day_id IN ARRAY v_day_ids
    LOOP
        UPDATE day d
        SET
            total_calories = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.calories)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_id
            ), 0),
            total_proteins = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.proteins)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_id
            ), 0),
            total_fats = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.fats)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_id
            ), 0),
            total_carbohydrates = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.carbohydrates)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_id
            ), 0)
        WHERE d.id = v_day_id;
    END LOOP;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recalculate_day_totals
    AFTER INSERT OR UPDATE OR DELETE ON list_ingredients
    FOR EACH ROW
    EXECUTE FUNCTION recalculate_day_totals();


CREATE OR REPLACE FUNCTION recalculate_days_for_ingredient_change()
RETURNS TRIGGER AS $$
DECLARE
    v_day_record RECORD;
BEGIN
    FOR v_day_record IN
        SELECT DISTINCT li.id_day
        FROM list_ingredients li
        WHERE li.id_ingredient = NEW.id
    LOOP
        UPDATE day d
        SET
            total_calories = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.calories)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_record.id_day
            ), 0),
            total_proteins = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.proteins)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_record.id_day
            ), 0),
            total_fats = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.fats)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_record.id_day
            ), 0),
            total_carbohydrates = COALESCE((
                SELECT SUM((li.weight / 100.0) * i.carbohydrates)
                FROM list_ingredients li
                JOIN ingredient i ON li.id_ingredient = i.id
                WHERE li.id_day = v_day_record.id_day
            ), 0)
        WHERE d.id = v_day_record.id_day;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recalculate_days_for_ingredient_change
    AFTER UPDATE OF calories, proteins, fats, carbohydrates ON ingredient
    FOR EACH ROW
    EXECUTE FUNCTION recalculate_days_for_ingredient_change();

-- ============================================
-- 7. TRIGGER: Log user metrics
-- ============================================
CREATE OR REPLACE FUNCTION log_user_metrics_change()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_metrics_history (
        username, 
        age, bmr, gender, goal,
        height, weight,
        norm_calories, norm_proteins, norm_fats, norm_carbohydrates,
        recorded_at
    ) VALUES (
        NEW.username, 
        NEW.age, NEW.bmr, NEW.gender, NEW.goal,
        NEW.height, NEW.weight,
        NEW.norm_calories, NEW.norm_proteins, NEW.norm_fats, NEW.norm_carbohydrates,
        CURRENT_TIMESTAMP
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_log_user_metrics
    AFTER INSERT OR UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION log_user_metrics_change();