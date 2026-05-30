-- ============================================
-- 0. EXTENSIONS & ENUM TYPES
-- ============================================
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
    CREATE TYPE user_goal AS ENUM ('weight_loss', 'weight_maintenance', 'weight_gain');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE user_gender AS ENUM ('m', 'w', 'None');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================
-- 1. USERS
-- ============================================
CREATE TABLE users (
    username VARCHAR(255) NOT NULL PRIMARY KEY,
    hash_password VARCHAR(255) NOT NULL,
    age INT NOT NULL CHECK (age BETWEEN 10 AND 120),
    bmr DECIMAL(6,4) NOT NULL CHECK (bmr BETWEEN 0.5 AND 5.0),
    lifestyle_description TEXT,
    gender user_gender NOT NULL DEFAULT 'None',
    goal user_goal NOT NULL DEFAULT 'weight_maintenance',
    height DECIMAL(5,1) NOT NULL CHECK (height BETWEEN 50 AND 250),
    weight DECIMAL(5,1) NOT NULL CHECK (weight BETWEEN 20 AND 500),
    norm_calories DECIMAL(6,1) NOT NULL CHECK (norm_calories BETWEEN 400 AND 10000),
    norm_proteins DECIMAL(6,1) NOT NULL CHECK (norm_proteins BETWEEN 0 AND 1000),
    norm_fats DECIMAL(6,1) NOT NULL CHECK (norm_fats BETWEEN 0 AND 1000),
    norm_carbohydrates DECIMAL(6,1) NOT NULL CHECK (norm_carbohydrates BETWEEN 0 AND 1000)
);

CREATE INDEX idx_users_goal ON users(goal);

-- ============================================
-- 2. USER METRICS HISTORY
-- ============================================
CREATE TABLE user_metrics_history (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    age INT NOT NULL,
    bmr DECIMAL(6,4) NOT NULL,
    gender user_gender NOT NULL,
    goal user_goal NOT NULL DEFAULT 'weight_maintenance',
    height DECIMAL(5,1) NOT NULL,
    weight DECIMAL(5,1) NOT NULL,
    norm_calories DECIMAL(6,1) NOT NULL,
    norm_proteins DECIMAL(6,1) NOT NULL,
    norm_fats DECIMAL(6,1) NOT NULL,
    norm_carbohydrates DECIMAL(6,1) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);

CREATE INDEX idx_metrics_username ON user_metrics_history(username);
CREATE INDEX idx_metrics_username_date ON user_metrics_history(username, recorded_at);

-- ============================================
-- 3. DAY (Daily Nutrition Summary)
-- ============================================
CREATE TABLE day (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_username VARCHAR(255) NOT NULL DEFAULT 'admin',
    calories DECIMAL(6,1) DEFAULT 0,
    proteins DECIMAL(6,1) DEFAULT 0,
    fats DECIMAL(6,1) DEFAULT 0,
    carbohydrates DECIMAL(6,1) DEFAULT 0,
    embedding VECTOR(384),
    UNIQUE (name, owner_username),
    FOREIGN KEY (owner_username) REFERENCES users(username) ON DELETE CASCADE
);

CREATE INDEX idx_ingredient_embedding ON ingredient USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_ingredient_owner ON ingredient(owner_username);
CREATE INDEX idx_ingredient_owner_name ON ingredient(owner_username, name);

-- ============================================
-- 5. LIST_INGREDIENTS (Junction Table)
-- ============================================
CREATE TABLE list_ingredients (
    id SERIAL PRIMARY KEY,
    id_day INT NOT NULL,
    id_ingredient INT NOT NULL,
    weight DECIMAL(6,1) DEFAULT 0 CHECK (weight >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_day) REFERENCES day(id) ON DELETE CASCADE,
    FOREIGN KEY (id_ingredient) REFERENCES ingredient(id) ON DELETE CASCADE,
    UNIQUE (id_day, id_ingredient)
);

CREATE INDEX idx_list_ingredients_id_day ON list_ingredients(id_day);
CREATE INDEX idx_list_ingredients_id_ingredient ON list_ingredients(id_ingredient);

-- ============================================
-- 6. TRIGGER: Recalculate Day Totals
-- ============================================
CREATE OR REPLACE FUNCTION recalculate_day_totals()
RETURNS TRIGGER AS $$
DECLARE v_day_id INT;
BEGIN
  IF TG_OP = 'INSERT' THEN
    FOR v_day_id IN SELECT DISTINCT id_day FROM new_rows LOOP
      PERFORM update_day_totals(v_day_id);
    END LOOP;

  ELSIF TG_OP = 'DELETE' THEN
    FOR v_day_id IN SELECT DISTINCT id_day FROM old_rows LOOP
      PERFORM update_day_totals(v_day_id);
    END LOOP;

  ELSIF TG_OP = 'UPDATE' THEN
    FOR v_day_id IN SELECT DISTINCT id_day FROM (SELECT id_day FROM new_rows UNION SELECT id_day FROM old_rows) t LOOP
      PERFORM update_day_totals(v_day_id);
    END LOOP;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_day_totals(day_id INT) RETURNS void AS $$
BEGIN
  UPDATE day d SET
    total_calories     = COALESCE(t.sum_cal, 0),
    total_proteins     = COALESCE(t.sum_prot, 0),
    total_fats         = COALESCE(t.sum_fat, 0),
    total_carbohydrates= COALESCE(t.sum_carb, 0)
  FROM (
    SELECT li.id_day,
           SUM((li.weight / 100.0) * i.calories)     AS sum_cal,
           SUM((li.weight / 100.0) * i.proteins)     AS sum_prot,
           SUM((li.weight / 100.0) * i.fats)         AS sum_fat,
           SUM((li.weight / 100.0) * i.carbohydrates) AS sum_carb
    FROM list_ingredients li
    JOIN ingredient i ON li.id_ingredient = i.id
    WHERE li.id_day = day_id
    GROUP BY li.id_day
  ) t
  WHERE d.id = t.id_day;

  IF NOT FOUND THEN
    UPDATE day SET total_calories=0, total_proteins=0, total_fats=0, total_carbohydrates=0 WHERE id = day_id;
  END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_calc_day_ins ON list_ingredients;
DROP TRIGGER IF EXISTS trigger_calc_day_upd ON list_ingredients;
DROP TRIGGER IF EXISTS trigger_calc_day_del ON list_ingredients;

CREATE TRIGGER trigger_calc_day_ins AFTER INSERT ON list_ingredients
  REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_day_totals();
CREATE TRIGGER trigger_calc_day_upd AFTER UPDATE ON list_ingredients
  REFERENCING NEW TABLE AS new_rows OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_day_totals();
CREATE TRIGGER trigger_calc_day_del AFTER DELETE ON list_ingredients
  REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_day_totals();


-- ============================================
-- 7. TRIGGER: Recalculate on Ingredient Change
-- ============================================
CREATE OR REPLACE FUNCTION recalculate_days_for_ingredient_change()
RETURNS TRIGGER AS $$
DECLARE v_day_id INT;
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NULL;

  ELSIF TG_OP = 'DELETE' THEN
    FOR v_day_id IN 
      SELECT DISTINCT li.id_day FROM list_ingredients li
      WHERE li.id_ingredient IN (SELECT id FROM old_rows)
    LOOP
      PERFORM update_day_totals(v_day_id);
    END LOOP;

  ELSIF TG_OP = 'UPDATE' THEN
    FOR v_day_id IN 
      WITH changed AS (
        SELECT n.id FROM new_rows n JOIN old_rows o USING (id)
        WHERE (n.calories IS DISTINCT FROM o.calories OR
               n.proteins IS DISTINCT FROM o.proteins OR
               n.fats IS DISTINCT FROM o.fats OR
               n.carbohydrates IS DISTINCT FROM o.carbohydrates)
      )
      SELECT DISTINCT li.id_day FROM list_ingredients li
      WHERE li.id_ingredient IN (SELECT id FROM changed)
    LOOP
      PERFORM update_day_totals(v_day_id);
    END LOOP;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_calc_ing_ins ON ingredient;
DROP TRIGGER IF EXISTS trigger_calc_ing_upd ON ingredient;
DROP TRIGGER IF EXISTS trigger_calc_ing_del ON ingredient;

CREATE TRIGGER trigger_calc_ing_ins AFTER INSERT ON ingredient
  REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_days_for_ingredient_change();
CREATE TRIGGER trigger_calc_ing_upd AFTER UPDATE ON ingredient
  REFERENCING NEW TABLE AS new_rows OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_days_for_ingredient_change();
CREATE TRIGGER trigger_calc_ing_del AFTER DELETE ON ingredient
  REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION recalculate_days_for_ingredient_change();

-- ============================================
-- 8. TRIGGER: Log User Metrics
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