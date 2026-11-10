SELECT *
FROM crosstab(
             $$SELECT f.name,
                      en.number,
                      SUM(fw.quantity)
               FROM feed_writeoff fw
                        JOIN feed_batch fb ON fw.batch_id = fb.batch_id
                        JOIN feed f ON fb.feed_id = f.feed_id
                        JOIN enclosure en ON fw.enclosure_id = en.enclosure_id
               WHERE fw.status = 'проведено'
                 AND fw.created_at BETWEEN '2025-01-01' AND '2025-06-30'
               GROUP BY f.name, en.number
               ORDER BY 1, 2$$,
             $$SELECT number
               FROM enclosure
               ORDER BY number$$
     ) AS ct(feed text,
             "A-01" numeric, "A-02" numeric, "A-03" numeric, "A-04" numeric,
             "A-05" numeric, "A-06" numeric, "A-07" numeric, "A-08" numeric,
             "B-01" numeric, "B-02" numeric, "B-03" numeric, "B-04" numeric, "B-05" numeric, "B-06" numeric,
             "Q-01" numeric, "Q-02" numeric, "Q-03" numeric,
             "V-01" numeric, "V-02" numeric);