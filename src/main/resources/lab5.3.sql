WITH participants AS (SELECT fp.bird_id,
                             f.flight_id,
                             f.type,
                             f.distance_km,
                             f.start_time,
                             f.end_time,
                             fp.place
                      FROM flight_participation fp
                               JOIN flight f ON fp.flight_id = f.flight_id
                      WHERE fp.status = 'завершено'
                        AND f.status = 'проведён'
                        AND fp.place IS NOT NULL
                        AND f.start_time >= '2025-07-01'
                        AND f.start_time < '2026-01-01'),

     dedup AS (SELECT p1.*
               FROM participants p1
               WHERE NOT EXISTS(SELECT 1
                                FROM participants p2
                                WHERE p1.bird_id = p2.bird_id
                                  AND p1.flight_id <> p2.flight_id
                                  AND p1.start_time < p2.end_time
                                  AND p2.start_time < p1.end_time
                                  AND (p2.distance_km > p1.distance_km OR
                                       (p2.distance_km = p1.distance_km AND p2.flight_id < p1.flight_id)))),

     bird_stats AS (SELECT bird_id,
                           COUNT(*)                                      AS flights,
                           SUM(distance_km)                              AS total_km,
                           ROUND(AVG(place), 1)                          AS avg_place,
                           MIN(place)                                    AS best_place,
                           COUNT(*) FILTER (WHERE type = 'тренировка')   AS trainings,
                           COUNT(*) FILTER (WHERE type = 'соревнование') AS competitions,
                           MAX(start_time)                               AS last_flight
                    FROM dedup
                    GROUP BY bird_id
                    HAVING COUNT(*) >= 3
                        OR MIN(place) <= 3),

     exams AS (SELECT bs.bird_id,
                      COUNT(vet_ex.examination_id) AS exams
               FROM bird_stats bs
                        LEFT JOIN vet_examination vet_ex ON bs.bird_id = vet_ex.bird_id
                   AND vet_ex.exam_date >= '2025-07-01'
                   AND vet_ex.exam_date <= bs.last_flight::date
               GROUP BY bs.bird_id)

SELECT b.ring_number                                             AS ring_number,
       b.name                                                    AS bird_name,
       br.name                                                   AS breed,
       b.sex                                                     AS sex,
       extract(year FROM age('2025-12-31', b.birth_date)) * 12
           + extract(month FROM age('2025-12-31', b.birth_date)) AS age_months,
       bs.flights                                                AS flights,
       bs.total_km                                               AS total_km,
       bs.avg_place                                              AS avg_place,
       bs.best_place                                             AS best_place,
       bs.trainings                                              AS trainings,
       bs.competitions                                           AS competitions,
       e.exams                                                   AS exams_before_last_flight
FROM bird_stats bs
         JOIN bird b ON b.bird_id = bs.bird_id
         JOIN breed br ON br.breed_id = b.breed_id
         JOIN exams e ON e.bird_id = bs.bird_id
ORDER BY avg_place, flights DESC, ring_number;