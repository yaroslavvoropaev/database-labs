WITH moves AS (SELECT enclosure_id,
                      COUNT(m.from_enclosure_id) FILTER ( WHERE m.from_enclosure_id = en.enclosure_id ) AS dep_cnt,
                      count(*) FILTER ( WHERE m.to_enclosure_id = en.enclosure_id )                     AS arr_cnt,
                      MAX(m.date)                                                                       AS last_move
               FROM enclosure en
                        JOIN movement m ON en.enclosure_id IN (m.from_enclosure_id, to_enclosure_id)
               WHERE m.date BETWEEN '2025-01-01' AND '2025-03-31'
               GROUP BY enclosure_id),
     stays AS (SELECT m.bird_id,
                      m.to_enclosure_id     AS enclosure_id,
                      m.date                AS from_d,
                      COALESCE(LEAD(m.date) OVER (PARTITION BY m.bird_id ORDER BY m.date),
                               b.left_date) AS to_d
               FROM movement m
                        JOIN bird b ON b.bird_id = m.bird_id),

     days AS (SELECT generate_series('2025-01-01'::date, '2025-03-31'::date, '1 day')::date AS day),


     daily AS (SELECT en.enclosure_id,
                      d.day,
                      COUNT(s.bird_id) AS birds_cnt
               FROM enclosure en
                        CROSS JOIN days d
                        LEFT JOIN stays s ON s.enclosure_id = en.enclosure_id
                   AND s.from_d <= d.day
                   AND (s.to_d IS NULL OR s.to_d > d.day)
               GROUP BY en.enclosure_id, d.day),

     occupancy AS (SELECT d.enclosure_id,
                          MAX(birds_cnt)                                     AS max_birds,
                          round(AVG(birds_cnt), 1)                           AS avg_birds,
                          COUNT(*) FILTER ( WHERE d.birds_cnt > en.capacity) AS days_over
                   FROM daily d
                            JOIN enclosure en ON en.enclosure_id = d.enclosure_id
                   GROUP BY d.enclosure_id),

     quarantine_birds AS (SELECT en.enclosure_id,
                                 COUNT(DISTINCT s.bird_id) AS cnt_quar_birds
                          FROM stays s
                                   JOIN enclosure en ON s.enclosure_id = en.enclosure_id
                          WHERE en.status = 'карантинный'
                            AND s.from_d <= '2025-03-31'
                            AND (s.to_d IS NULL OR s.to_d > '2025-01-01')
                          GROUP BY en.enclosure_id)

SELECT en.number                      AS enclosure_number,
       en.status                      AS status,
       en.capacity                    AS capacity,
       COALESCE(oc.max_birds, 0)      AS max_birds,
       COALESCE(oc.days_over, 0)      AS days_over,
       COALESCE(oc.avg_birds, 0)      AS avg_birds,
       COALESCE(m.dep_cnt, 0)         AS dep_cnt,
       COALESCE(m.arr_cnt, 0)         AS arr_cnt,
       COALESCE(qb.cnt_quar_birds, 0) AS quar_cnt,
       last_move                      AS last_move
FROM enclosure en
         LEFT JOIN occupancy oc ON oc.enclosure_id = en.enclosure_id
         LEFT JOIN moves m ON m.enclosure_id = en.enclosure_id
         LEFT JOIN quarantine_birds qb ON qb.enclosure_id = en.enclosure_id
ORDER BY max_birds DESC;
