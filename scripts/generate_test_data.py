#!/usr/bin/env python3
"""Генерация тестовых данных для БД голубиной фермы.

Запускать после schema.sql и seed.sql. Скрипт очищает тестовые таблицы и заполняет
их случайными данными, которые проходят все ограничения схемы. Кроме того:
птенцы младше родителей, вылупились из яиц кладки своей пары и наследуют породу
одного из родителей, события птицы происходят после её рождения, а корма
списывается не больше, чем есть в партии. Каждый год создаются близкородственные
пары (брат и сестра по отцу), часть пар идёт без разрешения (approved_by = NULL).
"""
import random
import string
from datetime import date, datetime, time, timedelta, timezone

import psycopg

DSN = 'host=localhost port=5432 dbname=chicken-farm user=chicken-farm password=chicken-farm'
TODAY = date(2026, 10, 1)
TZ = timezone(timedelta(hours=3))

# Объём данных
FOUNDERS = 60            # птицы без родителей, с которых начинается разведение
YEARS = range(2020, 2026)
PAIRS_PER_YEAR = 30
CLOSE_PAIRS_PER_YEAR = 5  # пары птиц с общим отцом, сверх случайных
BUYERS = 50
FLIGHTS = 80
FEED_BATCHES = 40
WRITEOFFS = 800
CONTRACTS = 80
DEATHS = 15

random.seed(42)  # одинаковые данные при каждом запуске

BIRD_NAMES = ['Ветер', 'Стрела', 'Гром', 'Буран', 'Сокол', 'Искра', 'Молния', 'Беркут',
              'Вихрь', 'Ласточка', 'Звезда', 'Метель', 'Уголёк', 'Агат', 'Янтарь', 'Луна']
FIRST_NAMES = ['Александр', 'Михаил', 'Николай', 'Евгений', 'Виктор', 'Олег', 'Роман', 'Игорь']
LAST_NAMES = ['Лебедев', 'Козлов', 'Морозов', 'Егоров', 'Павлов', 'Голубев', 'Орлов', 'Белов']
DIAGNOSES = ['Глистная инвазия', 'Трихомоноз', 'Насморк', 'Травма крыла', 'Лёгкое истощение']
QUARANTINE_REASONS = ['Подозрение на орнитоз', 'Контакт с больной птицей', 'Трихомоноз']

# Все коды вида A-07 или AB-07 в случайном порядке — уникальные номера колец и документов
CODES = [f'{a}{b}-{n:02d}' for a in string.ascii_uppercase
         for b in ['', *string.ascii_uppercase] for n in range(100)]
random.shuffle(CODES)
codes = iter(CODES)


def rand_date(start, end):
    return start + timedelta(days=random.randint(0, max(0, (end - start).days)))


def days(n):
    return timedelta(days=n)


def phone():
    return '+79' + ''.join(random.choices(string.digits, k=9))


with psycopg.connect(DSN) as conn:
    cur = conn.cursor()

    def insert(table, **values):
        """Вставляет одну строку и возвращает её id (первый столбец таблицы)."""
        sql = f'INSERT INTO {table} ({", ".join(values)}) VALUES ({", ".join(["%s"] * len(values))}) RETURNING *'
        return cur.execute(sql, list(values.values())).fetchone()[0]

    def select(sql):
        return cur.execute(sql).fetchall()

    cur.execute('TRUNCATE buyer, bird, breeding_pair, clutch, egg, movement, quarantine, vet_examination, '
                'treatment, vaccination, flight, flight_participation, feed_batch, feed_writeoff, '
                'transfer_contract RESTART IDENTITY CASCADE')

    # Справочники из seed.sql
    breeds = [r[0] for r in select('SELECT breed_id FROM breed')]
    employees = [r[0] for r in select('SELECT employee_id FROM employee')]
    feeds = [r[0] for r in select('SELECT feed_id FROM feed')]
    vaccines = [r[0] for r in select("SELECT drug_id FROM drug WHERE name LIKE 'Вакцина%'")]
    medicines = [r[0] for r in select("SELECT drug_id FROM drug WHERE name NOT LIKE 'Вакцина%'")]
    enclosures = select('SELECT enclosure_id, status FROM enclosure')
    breeding_enclosures = [e for e, status in enclosures if status == 'племенной']
    quarantine_enclosures = [e for e, status in enclosures if status == 'карантинный']

    for _ in range(BUYERS):
        insert('buyer', first_name=random.choice(FIRST_NAMES), last_name=random.choice(LAST_NAMES), phone=phone())

    # Птицы-основатели
    birds = []  # {'id', 'sex', 'birth', 'breed', 'father'}
    for i in range(FOUNDERS):
        sex, birth = 'МЖ'[i % 2], rand_date(date(2017, 1, 1), date(2018, 12, 31))
        breed = random.choice(breeds)
        bird_id = insert('bird', name=random.choice(BIRD_NAMES), ring_number=next(codes), sex=sex,
                         birth_date=birth, breed_id=breed)
        birds.append({'id': bird_id, 'sex': sex, 'birth': birth, 'breed': breed, 'father': None})

    # Разведение: пары -> кладки -> яйца -> птенцы
    for year in YEARS:
        adults = [b for b in birds if b['birth'] < date(year - 1, 3, 1)]
        males = [b for b in adults if b['sex'] == 'М']
        females = [b for b in adults if b['sex'] == 'Ж']
        n = min(PAIRS_PER_YEAR, len(males), len(females))
        pairs = list(zip(random.sample(males, n), random.sample(females, n)))
        siblings = [(m, f) for m in males for f in females if m['father'] and m['father'] == f['father']]
        pairs += random.sample(siblings, min(CLOSE_PAIRS_PER_YEAR, len(siblings)))
        for i, (male, female) in enumerate(pairs):
            start = rand_date(date(year, 2, 15), date(year, 3, 15))
            # близкородственные пары идут после случайных; каждая вторая из них — без разрешения
            no_permit = (i - n) % 2 == 0 if i >= n else random.random() < 0.1
            # часть пар последнего года ещё не распалась, часть доживает до следующего года
            end = None if year == YEARS[-1] and random.random() < 0.5 else date(year + random.randint(0, 1), 8, 31)
            pair = insert('breeding_pair', male_id=male['id'], female_id=female['id'], start_date=start,
                          end_date=end, approved_by=None if no_permit else random.choice(employees))
            for _ in range(random.randint(1, 2)):
                laid = rand_date(start + days(10), date(year, 7, 31))
                status = 'отменена' if random.random() < 0.1 else 'завершена'
                clutch = insert('clutch', pair_id=pair, enclosure_id=random.choice(breeding_enclosures),
                                date=laid, egg_count=2, status=status)
                for k in range(2):
                    egg = insert('egg', clutch_id=clutch, date=laid + days(2 * k))
                    if status == 'завершена' and random.random() < 0.8:
                        sex, birth = random.choice('МЖ'), laid + days(18 + 2 * k)
                        breed = random.choice([male['breed'], female['breed']])
                        bird_id = insert('bird', name=random.choice(BIRD_NAMES), ring_number=next(codes),
                                         sex=sex, birth_date=birth, egg_id=egg, breed_id=breed,
                                         father_id=male['id'], mother_id=female['id'])
                        birds.append({'id': bird_id, 'sex': sex, 'birth': birth, 'breed': breed,
                                      'father': male['id']})

    # События каждой птицы — после её рождения
    for b in birds:
        current, d = None, b['birth']
        for _ in range(random.randint(1, 4)):  # перемещения: откуда = куда переехала в прошлый раз
            d = rand_date(d + days(1), min(d + days(400), TODAY))
            to = random.choice([e for e, _ in enclosures if e != current])
            insert('movement', bird_id=b['id'], from_enclosure_id=current, to_enclosure_id=to,
                   employee_id=random.choice(employees), date=d)
            current = to

        for _ in range(2):  # осмотры; при диагнозе — лечение
            d = rand_date(b['birth'] + days(7), TODAY)
            healthy = random.random() < 0.8
            exam = insert('vet_examination', bird_id=b['id'], vet_id=random.choice(employees), exam_date=d,
                          result='Здоров' if healthy else random.choice(DIAGNOSES))
            if not healthy:
                insert('treatment', bird_id=b['id'], examination_id=exam, drug_id=random.choice(medicines),
                       responsible_id=random.choice(employees), start_date=d,
                       end_date=d + days(random.randint(5, 10)))

        insert('vaccination', bird_id=b['id'], drug_id=random.choice(vaccines), employee_id=random.choice(employees),
               date=rand_date(b['birth'] + days(30), TODAY), drug_batch=random.choice(CODES))

    for b in random.sample(birds, len(birds) // 10):
        start = rand_date(b['birth'] + days(30), TODAY)
        end = start + days(random.randint(14, 28))
        insert('quarantine', bird_id=b['id'], enclosure_id=random.choice(quarantine_enclosures),
               start_date=start, end_date=end if end <= TODAY else None, reason=random.choice(QUARANTINE_REASONS))

    # Вылеты: участвуют птицы старше 4 месяцев
    for i in range(1, FLIGHTS + 1):
        kind = random.choice(['тренировка', 'соревнование'])
        start = datetime.combine(rand_date(date(2020, 4, 1), TODAY + days(30)), time(7), TZ)
        distance = random.randint(20, 800)
        if start.date() > TODAY:
            status = 'запланирован'
        else:
            status = 'отменён' if random.random() < 0.1 else 'проведён'
        flight = insert('flight', name=f'{kind.capitalize()} №{i}', type=kind, route=f'Ферма — {distance} км',
                        distance_km=distance, start_time=start,
                        end_time=start + timedelta(hours=distance / 60 + 1), status=status)
        flyers = [b for b in birds if b['birth'] < start.date() - days(120)]
        for b in random.sample(flyers, min(len(flyers), random.randint(10, 30))):
            insert('flight_participation', flight_id=flight, bird_id=b['id'])

    # Корма: партии и списания (остаток партии не уходит в минус)
    batches = []
    for _ in range(FEED_BATCHES):
        received, quantity = rand_date(date(2020, 1, 1), TODAY), random.choice([250, 500, 1000])
        batches.append({'feed_id': random.choice(feeds), 'batch_number': next(codes), 'received_date': received,
                        'quantity': quantity, 'expiry_date': received + days(365), 'remaining': quantity})
    writeoffs = []
    for _ in range(WRITEOFFS):
        batch = random.choice(batches)
        quantity = min(batch['remaining'], random.randint(5, 40))
        if quantity > 0:
            batch['remaining'] -= quantity
            created = rand_date(batch['received_date'], min(batch['expiry_date'], TODAY))
            writeoffs.append((batch, quantity, datetime.combine(created, time(9), TZ)))
    for batch in batches:
        if batch['remaining'] == 0:
            status = 'израсходована'
        else:
            status = 'списана' if batch['expiry_date'] < TODAY else 'в наличии'
        batch['id'] = insert('feed_batch', status=status, **batch)
    for batch, quantity, created in writeoffs:
        insert('feed_writeoff', number=next(codes), created_at=created, batch_id=batch['id'],
               enclosure_id=random.choice(enclosures)[0], employee_id=random.choice(employees), quantity=quantity)

    # Передача птиц покупателям; по исполненному договору птица выбывает с фермы
    sold = random.sample(birds, CONTRACTS)
    for b in sold:
        start = rand_date(b['birth'] + days(60), TODAY)
        status = random.choice(['действует', 'исполнен', 'расторгнут'])
        end = None if status == 'действует' else min(start + days(14), TODAY)
        insert('transfer_contract', bird_id=b['id'], buyer_id=random.randint(1, BUYERS),
               employee_id=random.choice(employees), type=random.choice(['продажа', 'безвозмездная передача']),
               start_date=start, end_date=end,
               conditions=f'Цена {random.randrange(3000, 30000, 500)} руб.', status=status)
        if status == 'исполнен':
            cur.execute("UPDATE bird SET status = 'передана', left_date = %s WHERE bird_id = %s", (end, b['id']))

    # Падёж среди непроданных птиц
    for b in random.sample([b for b in birds if b not in sold], DEATHS):
        cur.execute("UPDATE bird SET status = 'пала', left_date = %s WHERE bird_id = %s",
                    (rand_date(b['birth'] + days(30), TODAY), b['id']))

    for table in ['bird', 'breeding_pair', 'egg', 'movement', 'vet_examination', 'flight_participation',
                  'feed_writeoff', 'transfer_contract']:
        print(f'{table:<22}{select(f"SELECT count(*) FROM {table}")[0][0]:>6}')
