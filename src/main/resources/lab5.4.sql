WITH months AS (SELECT g.month_start::date                          AS month_start,
                       extract(month FROM g.month_start)::int       AS month_num,
                       (ARRAY ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                           'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'])
                           [extract(month FROM g.month_start)::int] AS month_name
                FROM generate_series('2025-01-01'::date, '2025-12-01'::date, '1 month') AS g(month_start)),

     chicks AS (SELECT date_trunc('month', b.birth_date)::date AS month_start,
                       count(*)                                AS chicks
                FROM bird b
                WHERE b.egg_id IS NOT NULL
                  AND b.birth_date >= '2024-12-01'
                  AND b.birth_date < '2026-01-01'
                GROUP BY month_start),

     pairs AS (SELECT date_trunc('month', bp.start_date)::date AS month_start,
                      count(*)                                 AS pairs
               FROM breeding_pair bp
               WHERE bp.start_date >= '2025-01-01'
                 AND bp.start_date < '2026-01-01'
               GROUP BY month_start),

     clutches AS (SELECT date_trunc('month', c.date)::date AS month_start,
                         count(*)                          AS clutches
                  FROM clutch c
                  WHERE c.date >= '2025-01-01'
                    AND c.date < '2026-01-01'
                  GROUP BY month_start),

     vaccinations AS (SELECT date_trunc('month', v.date)::date AS month_start,
                             count(*)                          AS vaccinations
                      FROM vaccination v
                      WHERE v.date >= '2025-01-01'
                        AND v.date < '2026-01-01'
                      GROUP BY month_start),

     diagnoses AS (SELECT date_trunc('month', ve.exam_date)::date AS month_start,
                          count(*)                                AS diagnoses
                   FROM vet_examination ve
                   WHERE ve.result <> 'Здоров'
                     AND ve.exam_date >= '2025-01-01'
                     AND ve.exam_date < '2026-01-01'
                   GROUP BY month_start),

     feed AS (SELECT date_trunc('month', fw.created_at)::date AS month_start,
                     sum(fw.quantity)                         AS feed_kg
              FROM feed_writeoff fw
              WHERE fw.created_at >= '2025-01-01'
                AND fw.created_at < '2026-01-01'
                AND fw.status = 'проведено'
              GROUP BY month_start),

     contracts AS (SELECT date_trunc('month', tc.start_date)::date AS month_start,
                          count(*)                                 AS contracts
                   FROM transfer_contract tc
                   WHERE tc.start_date >= '2025-01-01'
                     AND tc.start_date < '2026-01-01'
                   GROUP BY month_start),

     chick_trend AS (SELECT g.month_start::date                                      AS month_start,
                            coalesce(c.chicks, 0)                                    AS chicks,
                            lag(coalesce(c.chicks, 0)) OVER (ORDER BY g.month_start) AS prev_chicks
                     FROM generate_series('2024-12-01'::date, '2025-12-01'::date, '1 month') AS g(month_start)
                              LEFT JOIN chicks c ON c.month_start = g.month_start)
SELECT m.month_name                                                               AS month_name,
       m.month_num                                                                AS month_num,
       ct.chicks                                                                  AS chicks,
       coalesce(p.pairs, 0)                                                       AS new_pairs,
       coalesce(cl.clutches, 0)                                                   AS clutches,
       coalesce(v.vaccinations, 0)                                                AS vaccinations,
       coalesce(d.diagnoses, 0)                                                   AS exams_with_diagnosis,
       coalesce(f.feed_kg, 0)                                                     AS feed_kg,
       coalesce(c.contracts, 0)                                                   AS contracts,
       round((ct.chicks - ct.prev_chicks) * 100.0 / nullif(ct.prev_chicks, 0), 1) AS chicks_change_pct
FROM months m
         LEFT JOIN chick_trend ct ON ct.month_start = m.month_start
         LEFT JOIN pairs p ON p.month_start = m.month_start
         LEFT JOIN clutches cl ON cl.month_start = m.month_start
         LEFT JOIN vaccinations v ON v.month_start = m.month_start
         LEFT JOIN diagnoses d ON d.month_start = m.month_start
         LEFT JOIN feed f ON f.month_start = m.month_start
         LEFT JOIN contracts c ON c.month_start = m.month_start
ORDER BY m.month_num;