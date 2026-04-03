CREATE TABLE users (
    users_name VARCHAR(255) NOT NULL PRIMARY KEY,
    hash_password VARCHAR(255) NOT NULL,
    height DECIMAL(5,1) NOT NULL,
    weight DECIMAL(5,1) NOT NULL,
    gender VARCHAR(5) CHECK (gender IN ('w', 'm', 'None'))
);

CREATE TABLE day (
    id SERIAL NOT NULL PRIMARY KEY,
    record_date DATE NOT NULL,
    users_name VARCHAR(255) NOT NULL,
    total_calories DECIMAL(6,1) DEFAULT 0,
    total_proteins DECIMAL(6,1) DEFAULT 0,
    total_fats DECIMAL(6,1) DEFAULT 0,
    total_carbohydrates DECIMAL(6,1) DEFAULT 0,
    UNIQUE (record_date, users_name),
    FOREIGN KEY (users_name) REFERENCES users(users_name) ON DELETE CASCADE
);

CREATE INDEX idx_day_users_date ON day(users_name, record_date);

CREATE TABLE ingredient (
    id SERIAL NOT NULL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    calories INT DEFAULT 0,
    proteins INT DEFAULT 0,
    fats INT DEFAULT 0,
    carbohydrates INT DEFAULT 0
);

CREATE TABLE list_ingredients (
    id SERIAL NOT NULL PRIMARY KEY,
    id_day INT NOT NULL,
    id_ingredient INT NOT NULL,
    weight DECIMAL(6,1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_day) REFERENCES day(id) ON DELETE CASCADE,
    FOREIGN KEY (id_ingredient) REFERENCES ingredient(id)
);

CREATE INDEX idx_list_ingredients_id_day ON list_ingredients(id_day);

CREATE OR REPLACE FUNCTION recalculate_day_totals()
RETURNS TRIGGER AS $$
DECLARE
    v_day_id INT;
    v_total_calories DECIMAL(6,1);
    v_total_proteins DECIMAL(6,1);
    v_total_fats DECIMAL(6,1);
    v_total_carbs DECIMAL(6,1);
    c_divisor CONSTANT DECIMAL := 100.0;
BEGIN
    IF TG_OP != 'DELETE' THEN
        v_day_id := NEW.id_day;
        
        SELECT 
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.calories), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.proteins), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.fats), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.carbohydrates), 0), 1)
        INTO v_total_calories, v_total_proteins, v_total_fats, v_total_carbs
        FROM list_ingredients li
        JOIN ingredient i ON li.id_ingredient = i.id
        WHERE li.id_day = v_day_id;

        UPDATE day SET 
            total_calories = v_total_calories,
            total_proteins = v_total_proteins,
            total_fats = v_total_fats,
            total_carbohydrates = v_total_carbs
        WHERE id = v_day_id;
    END IF;

    IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.id_day IS DISTINCT FROM NEW.id_day) THEN
        v_day_id := OLD.id_day;
        
        SELECT 
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.calories), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.proteins), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.fats), 0), 1),
            ROUND(COALESCE(SUM((li.weight / c_divisor) * i.carbohydrates), 0), 1)
        INTO v_total_calories, v_total_proteins, v_total_fats, v_total_carbs
        FROM list_ingredients li
        JOIN ingredient i ON li.id_ingredient = i.id
        WHERE li.id_day = v_day_id;

        UPDATE day SET 
            total_calories = v_total_calories,
            total_proteins = v_total_proteins,
            total_fats = v_total_fats,
            total_carbohydrates = v_total_carbs
        WHERE id = v_day_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_name
    AFTER INSERT OR UPDATE OR DELETE ON list_ingredients
    FOR EACH ROW
    EXECUTE FUNCTION recalculate_day_totals();