DROP TABLE IF EXISTS
    transfer_contract, feed_writeoff, feed_batch, flight_participation,
    vaccination, treatment, vet_examination, quarantine, movement,
    egg, clutch, breeding_pair, bird,
    flight, feed, enclosure, drug, buyer, employee, breed;



CREATE TABLE breed
(
    breed_id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        varchar(128) NOT NULL UNIQUE,
    description text
);

CREATE TABLE employee
(
    employee_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name  varchar(128),
    last_name   varchar(128),
    phone       varchar(32) CHECK (phone ~ '^\+[1-9][0-9]{9,14}$')
);

CREATE TABLE buyer
(
    buyer_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name varchar(128),
    last_name  varchar(128),
    phone      varchar(32) CHECK (phone ~ '^\+[1-9][0-9]{9,14}$')
);

CREATE TABLE drug
(
    drug_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    varchar(128) NOT NULL UNIQUE
);

CREATE TABLE enclosure
(
    enclosure_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    number       varchar(32) NOT NULL UNIQUE CHECK ( number ~ '^[A-Z]{1,2}-[0-9]{2}$'),
    status       varchar(32) NOT NULL CHECK (status in ('общий', 'племенной', 'карантинный', 'ветеринарный')),
    capacity     integer     NOT NULL CHECK (capacity > 0),
    location     text
);

CREATE TABLE feed
(
    feed_id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name               varchar(128) NOT NULL UNIQUE,
    type               varchar(32)  NOT NULL CHECK (type IN ('зерновая смесь', 'комбикорм')),
    storage_conditions text
);

CREATE TABLE flight
(
    flight_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        varchar(128)  NOT NULL UNIQUE,
    type        varchar(32)   NOT NULL CHECK (type IN ('тренировка', 'соревнование')),
    route       text,
    distance_km numeric(8, 2) NOT NULL CHECK (distance_km > 0),
    start_time  timestamptz   NOT NULL,
    end_time    timestamptz   NOT NULL,
    status      varchar(32)   NOT NULL DEFAULT 'запланирован'
        CHECK (status IN ('запланирован', 'проведён', 'отменён')),
    CHECK (end_time > start_time)
);

CREATE TABLE bird
(
    bird_id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        varchar(32),
    ring_number varchar(32) NOT NULL UNIQUE CHECK ( ring_number ~ '^[A-Z]{1,2}-[0-9]{2}$'),
    sex         char(1)     NOT NULL CHECK (sex IN ('М', 'Ж')),
    birth_date  date        NOT NULL,
    egg_id      integer,
    breed_id    integer     NOT NULL REFERENCES breed (breed_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    father_id   integer REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    mother_id   integer REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    status      varchar(32) NOT NULL DEFAULT 'на ферме'
        CHECK (status IN ('на ферме', 'передана', 'пала')),
    left_date   date,
    CHECK (father_id <> bird_id AND mother_id <> bird_id),
    CHECK ((status = 'на ферме') = (left_date IS NULL)),
    CHECK (left_date IS NULL OR left_date >= birth_date)
);

CREATE TABLE breeding_pair
(
    pair_id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    male_id     integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    female_id   integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    start_date  date    NOT NULL,
    end_date    date,
    approved_by integer REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CHECK (male_id <> female_id),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE clutch
(
    clutch_id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pair_id      integer     NOT NULL REFERENCES breeding_pair (pair_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    enclosure_id integer     NOT NULL REFERENCES enclosure (enclosure_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    date         date        NOT NULL,
    egg_count    integer     NOT NULL DEFAULT 0 CHECK (egg_count >= 0),
    status       varchar(32) NOT NULL DEFAULT 'инкубация' CHECK (status IN ('инкубация', 'завершена', 'отменена'))
);

CREATE TABLE egg
(
    egg_id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clutch_id integer NOT NULL REFERENCES clutch (clutch_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    date      date    NOT NULL
);

CREATE TABLE movement
(
    movement_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id           integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    from_enclosure_id integer REFERENCES enclosure (enclosure_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    to_enclosure_id   integer NOT NULL REFERENCES enclosure (enclosure_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    employee_id       integer NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    date              date    NOT NULL,
    CHECK (from_enclosure_id <> to_enclosure_id)
);

CREATE TABLE quarantine
(
    quarantine_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id       integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    enclosure_id  integer NOT NULL REFERENCES enclosure (enclosure_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    start_date    date    NOT NULL,
    end_date      date,
    reason        text    NOT NULL
);

CREATE TABLE vet_examination
(
    examination_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id        integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    vet_id         integer NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    exam_date      date    NOT NULL,
    result         text    NOT NULL
);

CREATE TABLE treatment
(
    treatment_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id        integer NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    examination_id integer REFERENCES vet_examination (examination_id) ON DELETE SET NULL ON UPDATE CASCADE,
    drug_id        integer NOT NULL REFERENCES drug (drug_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    responsible_id integer NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    start_date     date    NOT NULL,
    end_date       date    NOT NULL,
    CHECK (end_date >= start_date)
);

CREATE TABLE vaccination
(
    vaccination_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id        integer     NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    drug_id        integer     NOT NULL REFERENCES drug (drug_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    employee_id    integer     NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    date           date        NOT NULL,
    drug_batch     varchar(32) NOT NULL CHECK (drug_batch ~ '^[A-Z]{1,2}-[0-9]{2}$')
);


CREATE TABLE flight_participation
(
    flight_id integer     NOT NULL REFERENCES flight (flight_id) ON DELETE CASCADE ON UPDATE CASCADE,
    bird_id   integer     NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    status    varchar(32) NOT NULL DEFAULT 'заявлена'
        CHECK (status IN ('заявлена', 'завершено', 'сошла с дистанции')),
    place     integer CHECK (place > 0),
    PRIMARY KEY (flight_id, bird_id),
    UNIQUE (flight_id, place),
    CHECK (place IS NULL OR status = 'завершено')
);

CREATE TABLE feed_batch
(
    batch_id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feed_id       integer        NOT NULL REFERENCES feed (feed_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    batch_number  varchar(32)    NOT NULL CHECK (batch_number ~ '^[A-Z]{1,2}-[0-9]{2}$'),
    received_date date           NOT NULL,
    quantity      numeric(10, 2) NOT NULL CHECK (quantity > 0),
    expiry_date   date,
    remaining     numeric(10, 3) NOT NULL,
    status        varchar(20)    NOT NULL DEFAULT 'в наличии'
        CHECK (status IN ('в наличии', 'израсходована', 'списана')),
    UNIQUE (feed_id, batch_number),
    CHECK (remaining BETWEEN 0 AND quantity),
    CHECK (expiry_date IS NULL OR expiry_date >= received_date)
);

CREATE TABLE feed_writeoff
(
    writeoff_id  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    number       varchar(32)    NOT NULL UNIQUE CHECK (number ~ '^[A-Z]{1,2}-[0-9]{2}$'),
    created_at   timestamptz    NOT NULL DEFAULT now(),
    batch_id     integer        NOT NULL REFERENCES feed_batch (batch_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    enclosure_id integer        NOT NULL REFERENCES enclosure (enclosure_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    employee_id  integer        NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    quantity     numeric(10, 2) NOT NULL CHECK (quantity > 0)
);

CREATE TABLE transfer_contract
(
    contract_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bird_id     integer     NOT NULL REFERENCES bird (bird_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    buyer_id    integer     NOT NULL REFERENCES buyer (buyer_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    employee_id integer     NOT NULL REFERENCES employee (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    type        varchar(32) NOT NULL CHECK (type IN ('продажа', 'безвозмездная передача')),
    start_date  date        NOT NULL,
    end_date    date,
    conditions  text,
    status      varchar(32) NOT NULL DEFAULT 'действует'
        CHECK (status IN ('действует', 'исполнен', 'расторгнут')),
    CHECK ( (end_date IS NULL OR end_date >= start_date))
);


ALTER TABLE bird
    ADD CONSTRAINT bird_egg_id_fkey
        FOREIGN KEY (egg_id) REFERENCES egg (egg_id) ON DELETE RESTRICT ON UPDATE CASCADE;

