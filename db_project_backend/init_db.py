# init_db.py
import sqlite3

DB_PATH = "db_project.db"

schema_sql = """
DROP TABLE IF EXISTS Movie;
CREATE TABLE Movie(
    movie_id VARCHAR(15) PRIMARY KEY UNIQUE ,
    director_id VARCHAR(15),
    title VARCHAR(100) NOT NULL,
    release_year YEAR NOT NULL,
    duration INT NOT NULL,
    language CHAR(2) NOT NULL DEFAULT 'En',
    country VARCHAR(15) NOT NULL,
    FOREIGN KEY (director_id) REFERENCES Director(director_id)
);

Drop TABLE IF EXISTS Director;
CREATE TABLE Director(
    director_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(30) NOT NULL,
    birth_year YEAR NOT NULL,
    nationality VARCHAR(10) NOT NULL
);

DROP TABLE IF EXISTS Company;
CREATE TABLE Company(
    company_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(30) NOT NULL UNIQUE,
    founded_year YEAR NOT NULL,
    country VARCHAR(10) NOT NULL
);

DROP TABLE IF EXISTS Actor;
CREATE TABLE Actor(
    actor_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(30) NOT NULL,
    birth_year YEAR NOT NULL,
    nationality VARCHAR(10) NOT NULL,
    gender CHAR(1)
);

DROP TABLE IF EXISTS Role;
CREATE TABLE Role(
    role_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(30) NOT NULL
);

DROP TABLE IF EXISTS Genre;
CREATE TABLE Genre(
    genre_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(15) NOT NULL UNIQUE
);

DROP TABLE IF EXISTS User;
CREATE TABLE User(
    user_id VARCHAR(15) PRIMARY KEY UNIQUE,
    name VARCHAR(10) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE ,
    password VARCHAR(10) ,
    join_date DATE NOT NULL ,
    age TINYINT NOT NULL,
    CONSTRAINT age_range CHECK (age BETWEEN 0 AND 100)
);

DROP TABLE IF EXISTS Review;
CREATE TABLE Review(
    review_id VARCHAR(15) PRIMARY KEY UNIQUE,
    user_id VARCHAR(15) NOT NULL ,
    movie_id VARCHAR(15) NOT NULL ,
    rating TINYINT NOT NULL,
    comment TEXT NOT NULL,
    date DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES User(user_id),
    FOREIGN KEY (movie_id) REFERENCES Movie(movie_id)
);

DROP TABLE IF EXISTS Owns;
CREATE TABLE Owns(
    company_id VARCHAR(15) NOT NULL,
    movie_id VARCHAR(15) NOT NULL,
    PRIMARY KEY (company_id, movie_id),
    FOREIGN KEY (company_id) REFERENCES Company(company_id),
    FOREIGN KEY (movie_id) REFERENCES Movie(movie_id)
);

DROP TABLE IF EXISTS RoleInMovie_Played;
CREATE TABLE RoleInMovie_Played(
    role_id VARCHAR(15) NOT NULL,
    actor_id VARCHAR(15) NOT NULL,
    movie_id VARCHAR(15) NOT NULL,
    PRIMARY KEY (actor_id, movie_id),
    FOREIGN KEY (role_id) REFERENCES Role(role_id),
    FOREIGN KEY (actor_id) REFERENCES Actor(actor_id),
    FOREIGN KEY (movie_id) REFERENCES Movie(movie_id)
);

DROP TABLE IF EXISTS MovieGenre;
CREATE TABLE MovieGenre(
    genre_id VARCHAR(15) NOT NULL,
    movie_id VARCHAR(15) NOT NULL,
    PRIMARY KEY (genre_id, movie_id),
    FOREIGN KEY (genre_id) REFERENCES Genre(genre_id),
    FOREIGN KEY (movie_id) REFERENCES Movie(movie_id)
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("DB initialized.")


