#!/usr/bin/env python3

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
EPISODE_RATE = 0.08       # вероятность для птицы попасть за год на карантин или в стационар
REPAIR = (date(2025, 2, 10), date(2025, 2, 24), ['A-02', 'A-03'], 'A-01')  # с, по, откуда, куда
BUYERS = 50
FLIGHTS = 80
H2_2025_FLIGHTS = 20      # дополнительные полёты во втором полугодии 2025 года
OVERLAPS = 4              # полёты-«двойники» во 2-м полугодии 2025: 3 птицы записаны в оба полёта
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


def fits(b, start, end):
    """Можно ли увести птицу из своего вольера на [start, end] (end=None — до сих пор)."""
    if start <= b['settle'] or (end or TODAY) > b['bound']:
        return False
    # пересечения и даже касания запрещены, чтобы у птицы не было двух перемещений в один день
    return all(start > (e or date.max) or s > (end or date.max) for s, e, _ in b['away'])


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
    enclosures = select('SELECT enclosure_id, number, status, capacity FROM enclosure')
    by_number = {number: e for e, number, _, _ in enclosures}
    general = [(e, capacity) for e, _, status, capacity in enclosures if status == 'общий']
    breeding_enclosures = [e for e, _, status, _ in enclosures if status == 'племенной']
    quarantine_enclosures = [e for e, _, status, _ in enclosures if status == 'карантинный']
    hospital_enclosures = [e for e, _, status, _ in enclosures if status == 'ветеринарный']

    for _ in range(BUYERS):
        insert('buyer', first_name=random.choice(FIRST_NAMES), last_name=random.choice(LAST_NAMES), phone=phone())

    birds = []

    def add_bird(sex, birth, breed, arrival, first_enclosure, settle, **parents):
        """arrival — появление на ферме в first_enclosure, settle — переезд в свой общий вольер."""
        bird_id = insert('bird', name=random.choice(BIRD_NAMES), ring_number=next(codes), sex=sex,
                         birth_date=birth, breed_id=breed, **parents)
        home = random.choices([e for e, _ in general], weights=[c for _, c in general])[0]
        b = {'id': bird_id, 'sex': sex, 'birth': birth, 'breed': breed, 'father': parents.get('father_id'),
             'arrival': arrival, 'first_enclosure': first_enclosure, 'settle': settle, 'home': home,
             'away': [],               # отлучки из своего вольера: (с, по или None, вольер)
             'sick': [],               # карантин и стационар: (с, по) — в это время птица не летает
             'pair_until': date.min,   # окончание последней пары; date.max — пара ещё не распалась
             'bound': TODAY}           # последний день на ферме
        birds.append(b)
        return b

    # Птицы-основатели: поступают на ферму в начале 2019 года и 21 день сидят на карантине
    for i in range(FOUNDERS):
        arrival = rand_date(date(2019, 1, 10), date(2019, 4, 30))
        q = random.choice(quarantine_enclosures)
        b = add_bird('МЖ'[i % 2], rand_date(date(2017, 1, 1), date(2018, 12, 31)), random.choice(breeds),
                     arrival, q, arrival + days(21))
        insert('quarantine', bird_id=b['id'], enclosure_id=q, start_date=arrival, end_date=arrival + days(21),
               reason='Карантин после поступления на ферму')
        b['sick'].append((arrival, arrival + days(21)))

    # Разведение: пары -> кладки -> яйца -> птенцы; птица участвует не больше чем в одной паре за раз
    for year in YEARS:
        season = date(year, 2, 15)
        adults = [b for b in birds if b['birth'] < date(year - 1, 3, 1) and b['pair_until'] < season]
        males = [b for b in adults if b['sex'] == 'М']
        females = [b for b in adults if b['sex'] == 'Ж']
        n = min(PAIRS_PER_YEAR, len(males), len(females))
        pairs = list(zip(random.sample(males, n), random.sample(females, n)))
        used = {b['id'] for pair in pairs for b in pair}
        siblings = [(m, f) for m in males for f in females if m['father'] and m['father'] == f['father']]
        for m, f in random.sample(siblings, len(siblings)):
            if len(pairs) - n < CLOSE_PAIRS_PER_YEAR and m['id'] not in used and f['id'] not in used:
                pairs.append((m, f))
                used |= {m['id'], f['id']}
        for i, (male, female) in enumerate(pairs):
            start = rand_date(season, date(year, 3, 15))
            # близкородственные пары идут после случайных; каждая вторая из них — без разрешения
            no_permit = (i - n) % 2 == 0 if i >= n else random.random() < 0.1
            # часть пар последнего года ещё не распалась, часть доживает до следующего года
            end = None if year == YEARS[-1] and random.random() < 0.5 else date(year + random.randint(0, 1), 8, 31)
            enclosure = breeding_enclosures[i % len(breeding_enclosures)]
            pair = insert('breeding_pair', male_id=male['id'], female_id=female['id'], start_date=start,
                          end_date=end, approved_by=None if no_permit else random.choice(employees))
            for b in (male, female):
                b['away'].append((start, end, enclosure))
                b['pair_until'] = end or date.max
            for _ in range(random.randint(1, 2)):
                laid = rand_date(start + days(10), date(year, 7, 31))
                status = 'отменена' if random.random() < 0.1 else 'завершена'
                clutch = insert('clutch', pair_id=pair, enclosure_id=enclosure, date=laid, egg_count=2, status=status)
                for k in range(2):
                    egg = insert('egg', clutch_id=clutch, date=laid + days(2 * k))
                    if status == 'завершена' and random.random() < 0.8:
                        birth = laid + days(18 + 2 * k)
                        add_bird(random.choice('МЖ'), birth, random.choice([male['breed'], female['breed']]),
                                 birth, enclosure, birth + days(35),
                                 egg_id=egg, father_id=male['id'], mother_id=female['id'])

    # Выбытие решаем до событий: позже него у птицы ничего не происходит.
    # Птица выбывает только после своей последней пары; птицы из действующих пар не выбывают.
    def leave(b, left, status):
        b['bound'] = left - days(1)
        cur.execute('UPDATE bird SET status = %s, left_date = %s WHERE bird_id = %s', (status, left, b['id']))

    candidates = [b for b in birds if b['pair_until'] != date.max]
    sold = random.sample(candidates, CONTRACTS)
    for b in sold:
        earliest = max(b['birth'] + days(60), b['settle'], b['pair_until']) + days(1)
        if earliest > TODAY:
            continue
        start = rand_date(earliest, TODAY)
        status = random.choice(['действует', 'исполнен', 'расторгнут'])
        end = None if status == 'действует' else min(start + days(14), TODAY)
        insert('transfer_contract', bird_id=b['id'], buyer_id=random.randint(1, BUYERS),
               employee_id=random.choice(employees), type=random.choice(['продажа', 'безвозмездная передача']),
               start_date=start, end_date=end,
               conditions=f'Цена {random.randrange(3000, 30000, 500)} руб.', status=status)
        if status == 'исполнен':
            leave(b, end, 'передана')

    for b in random.sample([b for b in candidates if b not in sold], DEATHS):
        earliest = max(b['settle'], b['pair_until']) + days(1)
        if earliest <= TODAY:
            leave(b, rand_date(earliest, TODAY), 'пала')

    # Ремонт: птиц временно переводят в другой общий вольер, и он переполняется
    repair_start, repair_end, repaired, target = REPAIR
    for b in birds:
        if b['home'] in [by_number[n] for n in repaired] and fits(b, repair_start, repair_end):
            b['away'].append((repair_start, repair_end, by_number[target]))

    # Карантин и стационар: осмотр с диагнозом, лечение, перевод и возврат в свой вольер
    for b in birds:
        for year in range(2019, TODAY.year + 1):
            earliest, latest = max(date(year, 1, 1), b['settle'] + days(1)), min(date(year, 12, 31), b['bound'])
            if random.random() > EPISODE_RATE or earliest > latest:
                continue
            to_quarantine = random.random() < 0.7
            length = random.randint(14, 28) if to_quarantine else random.randint(5, 14)
            start = rand_date(earliest, latest)
            end = start + days(length)
            if end > b['bound']:
                if b['bound'] < TODAY:
                    continue      # птица выбудет раньше, чем закончится лечение
                end = None        # карантин или лечение ещё идут
            if not fits(b, start, end):
                continue
            enclosure = random.choice(quarantine_enclosures if to_quarantine else hospital_enclosures)
            reason = random.choice(QUARANTINE_REASONS if to_quarantine else DIAGNOSES)
            b['away'].append((start, end, enclosure))
            b['sick'].append((start, end or TODAY))
            exam = insert('vet_examination', bird_id=b['id'], vet_id=random.choice(employees), exam_date=start,
                          result=reason)
            insert('treatment', bird_id=b['id'], examination_id=exam, drug_id=random.choice(medicines),
                   responsible_id=random.choice(employees), start_date=start,
                   end_date=start + days(min(length, 10)))
            if to_quarantine:
                insert('quarantine', bird_id=b['id'], enclosure_id=enclosure, start_date=start, end_date=end,
                       reason=reason)

    # Перемещения: появление на ферме, переезд в свой вольер, затем каждая отлучка — туда и обратно
    for b in birds:
        steps = [(b['arrival'], b['first_enclosure'])]
        if b['settle'] <= b['bound']:
            steps.append((b['settle'], b['home']))
        for start, end, enclosure in sorted(b['away'], key=lambda a: a[0]):
            steps.append((start, enclosure))
            if end is not None:
                steps.append((end, b['home']))
        current = None
        for d, to in steps:
            if to != current:
                insert('movement', bird_id=b['id'], from_enclosure_id=current, to_enclosure_id=to,
                       employee_id=random.choice(employees), date=d)
                current = to

    # Плановые осмотры и вакцинация — пока птица на ферме
    for b in birds:
        for _ in range(2):
            d = rand_date(b['arrival'] + days(7), b['bound'])
            if d > b['bound']:
                continue
            healthy = random.random() < 0.8
            exam = insert('vet_examination', bird_id=b['id'], vet_id=random.choice(employees), exam_date=d,
                          result='Здоров' if healthy else random.choice(DIAGNOSES))
            if not healthy:
                insert('treatment', bird_id=b['id'], examination_id=exam, drug_id=random.choice(medicines),
                       responsible_id=random.choice(employees), start_date=d,
                       end_date=d + days(random.randint(5, 10)))
        d = rand_date(b['arrival'] + days(30), b['bound'])
        if d <= b['bound']:
            insert('vaccination', bird_id=b['id'], drug_id=random.choice(vaccines),
                   employee_id=random.choice(employees), date=d, drug_batch=random.choice(CODES))

    # Вылеты: участвуют птицы старше 4 месяцев, которые на ферме и не на карантине/лечении.
    # Обычно птица не попадает в два полёта одновременно. Места получают только долетевшие птицы.
    flown = {}  # bird_id -> [(начало, конец)] полётов птицы

    def add_flight(number, start, forced=(), status=None):
        """Создаёт полёт с участниками. forced — птицы, записанные в обход проверки наложений."""
        kind, distance = random.choice(['тренировка', 'соревнование']), random.randint(20, 800)
        end = start + timedelta(hours=distance / 60 + 1)
        if status is None and start.date() > TODAY:
            status = 'запланирован'
        elif status is None:
            status = 'отменён' if random.random() < 0.1 else 'проведён'
        flight_id = insert('flight', name=f'{kind.capitalize()} №{number}', type=kind, route=f'Ферма — {distance} км',
                           distance_km=distance, start_time=start, end_time=end, status=status)
        d = min(start.date(), TODAY)
        flyers = [b for b in birds if b['birth'] < start.date() - days(120) and b['arrival'] <= d <= b['bound']
                  and not any(s <= d <= e for s, e in b['sick'])
                  and not any(s < end and start < e for s, e in flown.get(b['id'], []))]
        chosen = list(forced) + random.sample(flyers, min(len(flyers), random.randint(10, 30)))
        random.shuffle(chosen)  # порядок участников — порядок прилёта
        participants, place = [], 0
        for b in chosen:
            flown.setdefault(b['id'], []).append((start, end))
            if status != 'проведён':
                result, bird_place = 'заявлена', None
            elif b not in forced and random.random() < 0.15:
                result, bird_place = 'сошла с дистанции', None
            else:
                place += 1  # у части долетевших место не указано
                result, bird_place = 'завершено', place if b in forced or random.random() < 0.9 else None
            insert('flight_participation', flight_id=flight_id, bird_id=b['id'], status=result, place=bird_place)
            participants.append((b, bird_place))
        return {'start': start, 'status': status, 'participants': participants}

    flight_dates = [rand_date(date(2020, 4, 1), TODAY + days(30)) for _ in range(FLIGHTS)]
    flight_dates += [rand_date(date(2025, 7, 1), date(2025, 12, 31)) for _ in range(H2_2025_FLIGHTS)]
    flights = [add_flight(i, datetime.combine(d, time(random.randint(5, 9)), TZ))
               for i, d in enumerate(sorted(flight_dates), 1)]

    # Двойная запись: несколько птиц попадают ещё и в полёт-«двойник», который идёт одновременно с их полётом
    second_half = [f for f in flights if f['status'] == 'проведён'
                   and date(2025, 7, 1) <= f['start'].date() <= date(2025, 12, 31)]
    for base in random.sample(second_half, OVERLAPS):
        finished = [b for b, place in base['participants'] if place is not None]
        flights.append(add_flight(len(flights) + 1, base['start'] + timedelta(minutes=random.randint(0, 60)),
                                  forced=random.sample(finished, min(3, len(finished))), status='проведён'))

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

    for table in ['bird', 'breeding_pair', 'egg', 'movement', 'quarantine', 'vet_examination',
                  'flight_participation', 'feed_writeoff', 'transfer_contract']:
        print(f'{table:<22}{select(f"SELECT count(*) FROM {table}")[0][0]:>6}')
