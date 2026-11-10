-- сводка по породам
WITH herd AS (SELECT b.breed_id,
                     COUNT(*)                                                                   AS birds_in_year,
                     COUNT(*) FILTER ( WHERE b.left_date IS NULL OR b.left_date > '2025-12-31') AS birds_at_end
              FROM bird b
              WHERE b.birth_date <= '2025-12-31'
                AND (b.left_date IS NULL
                  OR b.left_date >= '2025-01-01')
              GROUP BY b.breed_id),

     -- вспомагат
     pair_breed AS (SELECT br.*, b.breed_id
                    FROM breeding_pair br
                             JOIN bird b ON b.bird_id IN (br.male_id, br.female_id)),

     pairs AS (SELECT breed_id,
                      COUNT(DISTINCT pair_id) AS pairs
               FROM pair_breed
               WHERE start_date <= '2025-12-31'
                 AND (end_date IS NULL
                   OR end_date >= '2025-12-31')
               GROUP BY breed_id),

     clutches AS (SELECT breed_id,
                         COUNT(DISTINCT c.clutch_id) AS clutches,
                         COUNT(DISTINCT egg.egg_id)  AS eggs
                  FROM pair_breed
                           JOIN clutch c ON c.pair_id = pair_breed.pair_id
                           LEFT JOIN egg ON c.clutch_id = egg.clutch_id
                  WHERE c.date BETWEEN '2025-01-01' AND '2025-12-31'
                  GROUP BY breed_id),

     chicks AS (SELECT breed_id,
                       COUNT(*) AS chicks
                FROM bird b
                WHERE b.egg_id IS NOT NULL
                  AND b.birth_date BETWEEN '2025-01-01' AND '2025-12-31'
                GROUP BY breed_id),

     contracts AS (SELECT breed_id,
                          COUNT(*) AS contracts
                   FROM transfer_contract tc
                            JOIN bird b ON tc.bird_id = b.bird_id
                   WHERE tc.start_date BETWEEN '2025-01-01' AND '2025-12-31'
                   GROUP BY b.breed_id),

     exams AS (SELECT breed_id,
                      COUNT(*) AS exams
               FROM vet_examination vet_ex
                        JOIN bird b ON vet_ex.bird_id = b.bird_id
               WHERE vet_ex.exam_date BETWEEN '2025-01-01' AND '2025-12-31'
               GROUP BY b.breed_id),

     close_pairs AS (SELECT pair_breed.breed_id,
                            COUNT(DISTINCT pair_id)                                                 AS close_pairs,
                            COUNT(DISTINCT pair_id) FILTER ( WHERE pair_breed.approved_by IS NULL ) AS close_no_permit
                     FROM pair_breed
                              JOIN bird m ON pair_breed.male_id = m.bird_id
                              JOIN bird f ON pair_breed.female_id = f.bird_id
                     WHERE pair_breed.start_date BETWEEN '2025-01-01' AND '2025-12-31'
                       AND (m.bird_id = f.father_id
                         OR f.bird_id = m.mother_id
                         OR m.father_id = f.father_id
                         OR m.mother_id = f.mother_id)
                     GROUP BY pair_breed.breed_id)


SELECT br.name                         AS breed,
       COALESCE(h.birds_in_year, 0)    AS birds_in_year,
       COALESCE(h.birds_at_end, 0)     AS birds_at_end,
       COALESCE(p.pairs, 0)            AS pairs,
       COALESCE(c.clutches, 0)         AS clutches,
       COALESCE(c.eggs, 0)             AS eggs,
       COALESCE(ch.chicks, 0)          AS chicks,
       COALESCE(t.contracts, 0)        AS contracts,
       COALESCE(e.exams, 0)            AS exams,
       COALESCE(cp.close_pairs, 0)     AS close_pairs,
       COALESCE(cp.close_no_permit, 0) AS close_no_permit
FROM breed br
         LEFT JOIN herd h ON h.breed_id = br.breed_id
         LEFT JOIN pairs p ON p.breed_id = br.breed_id
         LEFT JOIN clutches c ON c.breed_id = br.breed_id
         LEFT JOIN chicks ch ON ch.breed_id = br.breed_id
         LEFT JOIN contracts t ON t.breed_id = br.breed_id
         LEFT JOIN exams e ON e.breed_id = br.breed_id
         LEFT JOIN close_pairs cp ON cp.breed_id = br.breed_id
ORDER BY birds_at_end DESC;



