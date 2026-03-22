/*
 * TB2 Data exploration
 *
 * We will set out to the understand the database structure,
 * 	and to understand how this data actually produces climbs on a Tension Board.
 *
 *
 * This data was downloaded via boardlib (https://github.com/lemeryfertitta/BoardLib) on 2026-03-14.
 * It is clear from the `kits` table that it was updated on 2026-01-22 (well, most of it).
 */

--------------------------------------------------------------------------------

/*
 * Understanding the board
 *
 * Goal:
 * 1. Shallow dive into the database structure
 * 2. Identify tha main tables
 * 3. Understand how the tension board data works, and how frames are mapped to board
 */

SELECT 'android_metadata' AS table_name, COUNT(*) AS rows FROM android_metadata
UNION ALL SELECT 'ascents', COUNT(*) FROM ascents
UNION ALL SELECT 'attempts', COUNT(*) FROM attempts
UNION ALL SELECT 'beta_links', COUNT(*) FROM beta_links
UNION ALL SELECT 'bids', COUNT(*) FROM bids
UNION ALL SELECT 'circuits', COUNT(*) FROM circuits
UNION ALL SELECT 'circuits_climbs', COUNT(*) FROM circuits_climbs
UNION ALL SELECT 'climb_cache_fields', COUNT(*) FROM climb_cache_fields
UNION ALL SELECT 'climb_random_positions', COUNT(*) FROM climb_random_positions
UNION ALL SELECT 'climb_stats', COUNT(*) FROM climb_stats
UNION ALL SELECT 'climbs', COUNT(*) FROM climbs
UNION ALL SELECT 'difficulty_grades', COUNT(*) FROM difficulty_grades
UNION ALL SELECT 'holes', COUNT(*) FROM holes
UNION ALL SELECT 'kits', COUNT(*) FROM kits
UNION ALL SELECT 'layouts', COUNT(*) FROM layouts
UNION ALL SELECT 'leds', COUNT(*) FROM leds
UNION ALL SELECT 'placement_roles', COUNT(*) FROM placement_roles
UNION ALL SELECT 'placements', COUNT(*) FROM placements
UNION ALL SELECT 'product_sizes', COUNT(*) FROM product_sizes
UNION ALL SELECT 'product_sizes_layouts_sets', COUNT(*) FROM product_sizes_layouts_sets
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'products_angles', COUNT(*) FROM products_angles
UNION ALL SELECT 'sets', COUNT(*) FROM sets
UNION ALL SELECT 'shared_syncs', COUNT(*) FROM shared_syncs
UNION ALL SELECT 'tags', COUNT(*) FROM tags
UNION ALL SELECT 'user_permissions', COUNT(*) FROM user_permissions
UNION ALL SELECT 'user_syncs', COUNT(*) FROM user_syncs
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'walls', COUNT(*) FROM walls
UNION ALL SELECT 'walls_sets', COUNT(*) FROM walls_sets
ORDER BY rows DESC;
/*
table_name                |rows  |
--------------------------+------+
climb_stats               |147046|
climbs                    |128762|
climb_cache_fields        | 90670|
beta_links                |  9500|
leds                      |  3388|
placements                |  1299|
holes                     |   967|
difficulty_grades         |    39|
attempts                  |    38|
product_sizes_layouts_sets|    36|
kits                      |    25|
products_angles           |    25|
shared_syncs              |    15|
product_sizes             |     9|
placement_roles           |     8|
sets                      |     6|
layouts                   |     3|
products                  |     2|
android_metadata          |     1|
ascents                   |     0|
bids                      |     0|
circuits                  |     0|
circuits_climbs           |     0|
climb_random_positions    |     0|
tags                      |     0|
user_permissions          |     0|
user_syncs                |     0|
users                     |     0|
walls                     |     0|
walls_sets                |     0|
 */


/*
 * It is clear that climb_stats (147k), climbs (128k), and climb_cache_fields (90k) are the most important.
 * beta_links just includes instagram links showing beta.
 *
 * Some Obesrvations:
 * - climb_stats has more entries than climbs -- potentially multiple entries per climb? Maybe same climb at different angles?
 * - placements/holes are likely reference tables for the physical board --hole positions, holds, etc.
 * - placement roles might be start/finish/middle/foot hold, etc. Or hold type?
 * - plenty of empty tables. Some should correspond to a specific user if you download the DB using broadlib with the -u flag. I couldn't get it working though.
 *
 * Let's start by looking at some sample data.
 */

--------------------------------------------------------


/*
 * CLIMBS
 */

SELECT * FROM climbs;
/*
uuid                            |layout_id|setter_id|setter_username|name          |description |hsm|edge_left|edge_right|edge_bottom|edge_top|angle|frames_count|frames_pace|frames                                   |is_draft|is_listed|created_at                |is_nomatch|
--------------------------------+---------+---------+---------------+--------------+------------+---+---------+----------+-----------+--------+-----+------------+-----------+-----------------------------------------+--------+---------+--------------------------+----------+
00163801596af1064d549ad75b684539|        9|    33802|vinsewah       |Duroxmanie 2.0|No matching |  3|        8|        88|         32|     128|     |           1|          0|p3r4p29r2p59r1p65r2p75r3p89r2p157r4p158r4|       0|        1|2021-02-16 09:13:28.000000|         1|
001945feb7509ce231c9d8b237082a39|        9|    30521|ssssss         |1 am          |            |  3|       24|        72|         56|     128|     |           1|          0|p18r1p22r1p57r2p70r2p149r3p161r4p162r4   |       0|        1|2021-02-13 01:53:03.000000|         0|
002078ce5b07166d80e87d2cafc94dab|        9|    61740|rockindude     |test69        |No matching.|  7|       24|        64|         64|     152|     |           1|          0|p16r2p49r1p70r2p83r3p127r2p140r2p191r1   |       0|        1|2021-12-22 03:41:04.000000|         1|
0027cc6eea485099809f5336a0452564|        9|    56399|memphisben     |Pre Game      |No matching.|  1|        8|        40|         40|     128|     |           1|          0|p22r1p49r1p74r3p76r4p78r2p80r2           |       0|        1|2021-02-13 01:52:54.000000|         1|
002e2db25b124ff5719afdb2c6732b2c|        9|    33924|jfisch040      |Yoooooooooo   |            |  9|       16|        48|          4|     152|     |           1|          0|p1r3p14r2p67r1p73r2p80r2p279r4           |       0|        1|2021-02-13 01:52:57.000000|         0|

 * The frams column is what actually determines the holds on the climb, and what role they are.
 * There are some climb characteristics (name, desceription, whether or not matching is allowed, setter info, edges, whether it is listed).
 * The UUID is how we link the specifc climb to the other tables.
 * What is hsm?
 */

SELECT * FROM climb_cache_fields;
/*
climb_uuid                      |ascensionist_count|display_difficulty|quality_average|
--------------------------------+------------------+------------------+---------------+
0004edf6aeac9618d96a3b949cd9a724|                 2|              24.0|            3.0|
00072fbd8c22711ef3532a5017c1a5c2|                 4|             19.25|            3.0|
00178ae931e482c3e6337d86d761936b|                 1|              27.0|            3.0|
0020974d7ee7f1b6d78b44a70f3fa27b|                 1|              24.0|            3.0|
0024b68ebc5cbbcfbe653ec4ed224271|                 1|              23.0|            3.0|
 *
 * climb_uuid, ascentionist_count, display difficulty, and quality_average.
 */

SELECT * FROM climb_stats;
/*
climb_uuid                      |angle|display_difficulty|benchmark_difficulty|ascensionist_count|difficulty_average|quality_average|fa_username         |fa_at              |
--------------------------------+-----+------------------+--------------------+------------------+------------------+---------------+--------------------+-------------------+
0004edf6aeac9618d96a3b949cd9a724|   40|              24.0|                    |                 2|              24.0|            3.0|david.p.kunz        |2020-03-23 23:52:37|
00072fbd8c22711ef3532a5017c1a5c2|   25|             19.25|                    |                 4|             19.25|            3.0|free.and.independent|2019-10-05 01:55:14|
0008d8af4649234054bea434aaeabaab|   45|              20.0|                    |                 2|              20.0|            2.0|judemandudeman      |2018-01-30 03:18:13|
000eb831d3a1e92ea8fdec2518fd77d3|   20|              18.0|                    |                 1|              18.0|            3.0|dasruch17           |2019-03-15 15:46:06|
000eb831d3a1e92ea8fdec2518fd77d3|   40|              23.0|                    |                 1|              23.0|            3.0|hunter.tension      |2021-06-27 22:41:10|
 *
 * So per UUID, we have a lot of the same info as climb_cache_fields.
 * We also have angle and first ascent information
 *
 *
 *
 * Why are there more climb_stats than climbs?
 * Let's see if it is due to multiple angles per climb.
 */

SELECT
    cs.climb_uuid,
    COUNT(*) AS angle_count
FROM climb_stats cs
GROUP BY cs.climb_uuid
ORDER BY angle_count DESC;
/*
climb_uuid                      |angle_count|
--------------------------------+-----------+
0227943857CA4D55849E8D351775B10A|         14|
18E0834CBBB64952AE12BB7DD7F56E28|         14|
197A52F20F424C3DB935993E2385758D|         14|
2048D3DB80DD443BA4BB37F263984929|         14|
2A740F4239AD4D498F65780626D7CECA|         14|
 *
 *
 * Yep, some UUIDs correspond to multiple angles.
 * 
 * How many climbs are there if we don't take angle into account?
 * 
 */

SELECT COUNT(DISTINCT climb_uuid) FROM climb_stats;
/*
 * 
COUNT(DISTINCT climb_uuid)|
--------------------------+
                     90494|
 * So 90k climbs in total.
 * 
 * Let's take a look at difficulty_grades.
 */

SELECT * FROM difficulty_grades;
/*
difficulty|boulder_name|route_name|is_listed|
----------+------------+----------+---------+
         1|1a/V0       |2b/5.1    |        0|
         2|1b/V0       |2c/5.2    |        0|
         3|1c/V0       |3a/5.3    |        0|
         4|2a/V0       |3b/5.3    |        0|
         5|2b/V0       |3c/5.4    |        0|
         6|2c/V0       |4a/5.5    |        0|
         7|3a/V0       |4b/5.6    |        0|
         8|3b/V0       |4c/5.7    |        0|
         9|3c/V0       |5a/5.8    |        0|
        10|4a/V0       |5b/5.9    |        1|
        11|4b/V0       |5c/5.10a  |        1|
        12|4c/V0       |6a/5.10b  |        1|
        13|5a/V1       |6a+/5.10c |        1|
        14|5b/V1       |6b/5.10d  |        1|
        15|5c/V2       |6b+/5.11a |        1|
        16|6a/V3       |6c/5.11b  |        1|
        17|6a+/V3      |6c+/5.11c |        1|
        18|6b/V4       |7a/5.11d  |        1|
        19|6b+/V4      |7a+/5.12a |        1|
        20|6c/V5       |7b/5.12b  |        1|
        21|6c+/V5      |7b+/5.12c |        1|
        22|7a/V6       |7c/5.12d  |        1|
        23|7a+/V7      |7c+/5.13a |        1|
        24|7b/V8       |8a/5.13b  |        1|
        25|7b+/V8      |8a+/5.13c |        1|
        26|7c/V9       |8b/5.13d  |        1|
        27|7c+/V10     |8b+/5.14a |        1|
        28|8a/V11      |8c/5.14b  |        1|
        29|8a+/V12     |8c+/5.14c |        1|
        30|8b/V13      |9a/5.14d  |        1|
        31|8b+/V14     |9a+/5.15a |        1|
        32|8c/V15      |9b/5.15b  |        1|
        33|8c+/V16     |9b+/5.15c |        1|
        34|9a/V17      |9c/5.15d  |        0|
        35|9a+/V18     |9c+/5.16a |        0|
        36|9b/V19      |10a/5.16b |        0|
        37|9b+/V20     |10a+/5.16c|        0|
        38|9c/V21      |10b/5.16d |        0|
        39|9c+/V22     |10b+/5.17a|        0|
 *
 * So this just tells us what the numeric value corresponds to in terms of a boulder grade or a route grade.
 */

--------------------------------------------------------

/*
 * BOARDS, PLACEMENTS and HOLDS
 */


SELECT * FROM placements;
/*
id|layout_id|hole_id|set_id|default_placement_role_id|
--+---------+-------+------+-------------------------+
 1|        9|      2|     8|                        3|
 2|        9|     10|     8|                        3|
 3|        9|    317|     8|                        1|
 4|        9|    325|     8|                        1|
 5|        9|    320|     8|                        1|
 *
 * So we have specific layouts, hole_id, set_id, and default_palcement_role_id.
 * Let's examine each of these, starting with layout.
 */

SELECT * FROM layouts;
/*
id|product_id|name                  |instagram_caption|is_mirrored|is_listed|password|created_at                |
--+----------+----------------------+-----------------+-----------+---------+--------+--------------------------+
10|         5|Tension Board 2 Mirror|                 |          1|        1|        |2022-08-19 14:52:19.570731|
11|         5|Tension Board 2 Spray |                 |          0|        1|        |2022-10-26 03:42:45.736011|
 9|         4|Original Layout       |                 |          1|        1|        |2017-01-01 00:45:51.000000|
 *
 * So this tells us which specific board, along with whether or not it is mirrored.
 * So both TB1 and TB2 Mirror are, while TB2 Spray is not.
 *
 * There is a distinction between product_id. I imagine it is just TB1 vs TB2.
 *
 */

SELECT * FROM products;
/*
id|name           |is_listed|password|min_count_in_frame|max_count_in_frame|
--+---------------+---------+--------+------------------+------------------+
 4|Tension Board  |        1|        |                 2|                35|
 5|Tension Board 2|        1|        |                 2|                35|
 *
 * Yep, product ID just tells us which board we're working with.
 *
 * May as well see product_sizes, produce_sizes_layouts_sets, and products_angles while we're at it.
 * Let's start with the latter, since it's self-explanatory.
 */

SELECT * FROM products_angles;
/*
product_id|angle|
----------+-----+
         4|   20|
         4|   25|
         4|   30|
         4|   35|
         4|   40|
         4|   45|
         4|   50|
         5|   20|
         5|   25|
         5|   30|
         5|   35|
         5|   40|
         5|   45|
         5|   50|
         5|   55|
         4|    0|
         4|    5|
         4|   10|
         4|   15|
         5|    0|
         5|    5|
         5|   10|
         5|   15|
         5|   60|
         5|   65|
 *
 * Yep, just tells us the angles that the TB1 and TB2 can go.
 * Let's look at the sizes.
 */

SELECT * FROM product_sizes;
/*
id|product_id|edge_left|edge_right|edge_bottom|edge_top|name             |description                      |image_filename        |position|is_listed|
--+----------+---------+----------+-----------+--------+-----------------+---------------------------------+----------------------+--------+---------+
 1|         4|        0|        96|          0|     156|Full Wall        |Rows: KB1, KB2, 1-18¶Columns: A-K|product_sizes/1.png   |       0|        1|
 2|         4|        0|        96|          4|     156|Half Kickboard   |Rows: KB2, 1-18¶Columns: A-K     |product_sizes/2.png   |       1|        1|
 3|         4|        0|        96|          8|     156|No Kickboard     |Rows: 1-18¶Columns: A-K          |product_sizes/3-v2.png|       2|        1|
 4|         4|        0|        96|          8|     132|Short            |Rows: 1-15¶Columns: A-K          |product_sizes/4-v2.png|       3|        1|
 5|         4|       16|        80|          8|     132|Short & Narrow   |Rows: 1-15¶Columns: B.5-I.5      |product_sizes/5-v3.png|       4|        1|
 6|         5|      -68|        68|          0|     144|12 high x 12 wide|                                 |product_sizes/6.png   |       1|        1|
 7|         5|      -68|        68|          0|     120|10 high x 12 wide|                                 |product_sizes/7.png   |       2|        1|
 8|         5|      -44|        44|          0|     144|12 high x 8 wide |                                 |product_sizes/8.png   |       3|        1|
 9|         5|      -44|        44|          0|     120|10 high x 8 wide |                                 |product_sizes/9.png   |       4|        1|
 *
 * This just gives us product_size_id, and some info.
 * We'll be mainly interested in the TB2 Mirror 12x12, so we want product_size_id=6.
 */

SELECT * FROM product_sizes_layouts_sets;
/*
id|product_size_id|layout_id|set_id|image_filename                                  |is_listed|
--+---------------+---------+------+------------------------------------------------+---------+
 1|              1|        9|     8|product_sizes_layouts_sets/1.png                |        1|
 2|              1|        9|     9|product_sizes_layouts_sets/2.png                |        1|
 3|              1|        9|    10|product_sizes_layouts_sets/3.png                |        1|
 4|              1|        9|    11|product_sizes_layouts_sets/4.png                |        1|
 5|              2|        9|     8|product_sizes_layouts_sets/5.png                |        1|
 6|              2|        9|     9|product_sizes_layouts_sets/6.png                |        1|
 7|              2|        9|    10|product_sizes_layouts_sets/7.png                |        1|
 8|              2|        9|    11|product_sizes_layouts_sets/8.png                |        1|
 9|              3|        9|     8|product_sizes_layouts_sets/9.png                |        1|
10|              3|        9|     9|product_sizes_layouts_sets/10.png               |        1|
11|              3|        9|    10|product_sizes_layouts_sets/11.png               |        1|
12|              3|        9|    11|product_sizes_layouts_sets/12.png               |        1|
13|              4|        9|     8|product_sizes_layouts_sets/13.png               |        1|
14|              4|        9|     9|product_sizes_layouts_sets/14.png               |        1|
15|              4|        9|    10|product_sizes_layouts_sets/15.png               |        1|
16|              4|        9|    11|product_sizes_layouts_sets/16.png               |        1|
17|              5|        9|     8|product_sizes_layouts_sets/17.png               |        1|
18|              5|        9|     9|product_sizes_layouts_sets/18.png               |        1|
19|              5|        9|    10|product_sizes_layouts_sets/19.png               |        1|
20|              5|        9|    11|product_sizes_layouts_sets/20.png               |        1|
23|              7|       10|    12|product_sizes_layouts_sets/23.png               |        1|
25|              8|       10|    12|product_sizes_layouts_sets/25.png               |        1|
26|              8|       10|    13|product_sizes_layouts_sets/26.png               |        1|
27|              9|       10|    12|product_sizes_layouts_sets/27.png               |        1|
28|              9|       10|    13|product_sizes_layouts_sets/28.png               |        1|
29|              6|       11|    12|product_sizes_layouts_sets/12x12-tb2-wood.png   |        1|
30|              6|       11|    13|product_sizes_layouts_sets/12x12-tb2-plastic.png|        1|
31|              7|       11|    12|product_sizes_layouts_sets/12x10-tb2-wood.png   |        1|
32|              7|       11|    13|product_sizes_layouts_sets/12x10-tb2-plastic.png|        1|
33|              8|       11|    12|product_sizes_layouts_sets/8x12-tb2-wood.png    |        1|
34|              8|       11|    13|product_sizes_layouts_sets/8x12-tb2-plastic.png |        1|
35|              9|       11|    12|product_sizes_layouts_sets/8x10-tb2-wood.png    |        1|
36|              9|       11|    13|product_sizes_layouts_sets/8x10-tb2-plastic.png |        1|
21|              6|       10|    12|product_sizes_layouts_sets/21-2.png             |        1|
22|              6|       10|    13|product_sizes_layouts_sets/22-2.png             |        1|
24|              7|       10|    13|product_sizes_layouts_sets/24-2.png             |        1|
 *
 * These tell the product_size_id, which might be useful later.
 * We'll mostly be interested in the TB2 12x12 Mirror, so thats product_id=6, layout_id=10.
 * This tells us which images we'll want to look at for later. We'll make some heat maps, so 21-2.png and 22-2.png are out pictures.
 * We'll combine them into one in GIMP and call it tb2_board_12x12_composite.png
 *
 * Back to understanding the placements. We'll look at holes next.
 */


SELECT * FROM holes;
/*
id|product_id|name|x |y  |mirrored_hole_id|mirror_group|
--+----------+----+--+---+----------------+------------+
 1|         4|A,18| 8|152|              11|           0|
 2|         4|B,18|16|152|              10|           0|
 3|         4|C,18|24|152|               9|           0|
 4|         4|D,18|32|152|               8|           0|
 5|         4|E,18|40|152|               7|           0|
 *
 * The coordinates must be the position on the board.
 * These make sense with the product sizes above -- it is clear what the boundaries are (from the edge features).
 *
 * With the TB1 and TB2 Mirror, you can mirror climbs. So the mirror_hole_id must be where the associated mirror hole is.
 * Not sure about the mirror_group.
 *
 * Let's look at sets next.
 */

SELECT * FROM sets;
/*
id|name    |hsm|
--+--------+---+
 8|Set A   |  1|
 9|Set B   |  2|
10|Set C   |  4|
11|Foot Set|  8|
12|Wood    |  1|
13|Plastic |  2|
 *
 * So these tell us the corresponding set of the board.
 * Any board will often use a combination: for example, the TB2 Mirror uses both wood and plastic.
 * No idea what hsm means. Probably something to do with "hold set ____"
 *
 * Next let's understand this default_placement_id. We'll look at placement_roles.
 */

SELECT * FROM placement_roles;
/*
id|product_id|position|name  |full_name|led_color|screen_color|
--+----------+--------+------+---------+---------+------------+
 1|         4|       1|start |Start    |00FF00   |00DD00      |
 3|         4|       3|finish|Finish   |FF0000   |FF0000      |
 4|         4|       4|foot  |Foot Only|FF00FF   |FF00FF      |
 5|         5|       1|start |Start    |00FF00   |00DD00      |
 7|         5|       3|finish|Finish   |FF0000   |FF0000      |
 8|         5|       4|foot  |Foot Only|FF00FF   |FF00FF      |
 2|         4|       2|middle|Middle   |0000FF   |0066FF      |
 6|         5|       2|middle|Middle   |0000FF   |0066FF      |
 *
 * These are indeed start/finish/middle/foot, but with 4 being for the TB1 and 4 being for the TB2.
 * So r5 = start, r6 = middle, r7 = finish, r8 = foot only on TB2. Similarly with r1-r4 on TB1.
 *
 * Also tells us which colours are used by the board and the app.
 *
 * Lastly, let's look at the LEDs table since it is one of the bigger ones, and the LEDs relate to the placements/holes.
 */

SELECT * FROM leds;
/*
id|product_size_id|hole_id|position|
--+---------------+-------+--------+
 1|              1|    379|       0|
 2|              1|    389|       1|
 3|              1|    378|       2|
 4|              1|    388|       3|
 5|              1|    377|       4|
 *
 * product_size_id tells us which size of board this led belongs to, and the hole_id tells us the corresponding hole.
 */

--------------------------

/*
 * STRAGGLERS
 *
 * Let's take a look at some of the non-empty tables that are left over.
 *
 */

SELECT * FROM beta_links;

/*
 * yep, just instagram links of people doing the climb..'
 *
 * what about attemps?
 */

SELECT * FROM attempts;
/*
id|position|name     |
--+--------+---------+
 1|       1|Flash    |
 2|       2|2 tries  |
 3|       3|3 tries  |
 4|       4|4 tries  |
 5|       5|5 tries  |
 6|       6|6 tries  |
 7|       7|7 tries  |
 8|       8|8 tries  |
 9|       9|9 tries  |
10|      10|10 tries |
11|     100|1 day    |
12|     200|2 days   |
13|     300|3 days   |
14|     400|4 days   |
15|     500|5 days   |
16|     600|6 days   |
17|     700|7 days   |
18|     800|8 days   |
19|     900|9 days   |
20|    1000|10 days  |
21|   10000|1 month  |
22|   20000|2 months |
23|   30000|3 months |
24|   40000|4 months |
25|   50000|5 months |
26|   60000|6 months |
27|   70000|7 months |
28|   80000|8 months |
29|   90000|9 months |
30|  100000|10 months|
31|  110000|11 months|
32|  120000|12 months|
33| 1000000|1 year   |
34| 2000000|2 years  |
35| 3000000|3 years  |
36| 4000000|4 years  |
37| 5000000|5 years  |
 0|       0|Unknown  |
 *
 * Not really sure what to make of this table.
 *
 * Let's do kits next.
 */

SELECT * FROM kits;
/*
serial_number|name                      |is_autoconnect|is_listed|created_at                |updated_at                |
-------------+--------------------------+--------------+---------+--------------------------+--------------------------+
84668        |TB2 Spray                 |             0|        1|2022-10-06 18:37:44.021720|2022-10-06 18:37:44.021720|
84669        |TB2 Mirror                |             0|        1|2022-10-06 18:37:33.495216|2022-10-06 18:37:33.495216|
84670        |TB1                       |             0|        1|2022-10-06 18:37:22.548024|2022-10-06 18:37:22.548024|
84685        |Tension Board             |             1|        1|2023-09-26 01:41:54.577139|2023-09-26 01:41:54.577139|
81114        |Tension Board 20 degrees  |             0|        1|2023-12-01 20:48:43.013655|2023-12-13 01:17:00.160708|
84771        |Tension Board 2 40 degrees|             0|        1|2023-12-01 20:48:22.110324|2023-12-13 01:16:36.884910|
84863        |Tension Board 1           |             0|        1|2024-04-05 18:15:05.684248|2024-04-05 18:15:05.684248|
84783        |Tension Board 2           |             0|        1|2024-04-05 18:15:20.260241|2024-04-05 18:15:20.260241|
81106        |Tension Board             |             0|        1|2024-07-24 18:18:43.531949|2024-07-24 18:18:43.531949|
84818        |Tension Board 2           |             0|        1|2024-07-24 18:19:00.103068|2024-07-24 18:19:00.103068|
84562        |Tension Board 1           |             0|        1|2025-01-22 01:20:51.718259|2025-01-22 01:20:51.718259|
84911        |Tension Board 2           |             0|        1|2025-01-22 01:21:06.579570|2025-01-22 01:21:06.579570|
84776        |Tension Board 2           |             0|        1|2025-02-26 20:15:08.355773|2025-02-26 20:15:08.355773|
84439        |Tension Board 20 degrees  |             0|        1|2023-12-01 20:49:00.365305|2025-04-17 03:00:37.331399|
81199        |Tension Board 1           |             0|        1|2025-05-12 23:08:24.829370|2025-05-12 23:08:24.829370|
841062       |Tension Board 2           |             0|        1|2025-05-12 23:08:41.275933|2025-05-12 23:08:41.275933|
84938        |Tension Board Mirror      |             0|        1|2025-09-18 23:12:12.029864|2025-09-18 23:12:12.029864|
84937        |Tension Board Spray       |             0|        1|2025-09-18 23:12:24.734650|2025-09-18 23:12:24.734650|
91396        |Tension Board Full        |             0|        1|2025-09-22 03:51:35.982550|2025-09-22 03:51:35.982550|
841139       |Tension Board 2           |             0|        1|2025-09-22 03:51:52.379943|2025-09-22 03:51:52.379943|
841066       |Tension Board Mirror      |             0|        1|2025-11-30 19:58:24.143556|2025-11-30 19:58:24.143556|
84983        |Tension Board Spray       |             0|        1|2025-11-30 19:58:40.803397|2025-11-30 19:58:40.803397|
84870        |Tension Board 2           |             0|        1|2025-12-12 17:52:43.951207|2025-12-12 17:52:43.951207|
841240       |Tension Board Left        |             0|        1|2026-01-22 20:08:37.220459|2026-01-22 20:08:37.220459|
91744        |Tension Board Right       |             0|        1|2026-01-22 20:08:48.978201|2026-01-22 20:08:48.978201|
*
* Not sure what to make of this table either. I guess just products they have? Some are fixed, some are not, and some are parts of the full board?
*
* Shared syncs next.
*/

SELECT * FROM shared_syncs;
/*
table_name                |last_synchronized_at      |
--------------------------+--------------------------+
attempts                  |2024-06-22 23:43:48.952599|
products                  |2024-06-22 23:43:48.952599|
product_sizes             |2024-06-22 23:43:48.952599|
holes                     |2024-06-22 23:43:48.952599|
leds                      |2024-06-22 23:43:48.952599|
sets                      |2024-06-22 23:43:48.952599|
products_angles           |2024-06-22 23:43:48.952599|
placements                |2024-06-22 23:43:48.952599|
product_sizes_layouts_sets|2024-06-25 18:11:42.775946|
layouts                   |2025-08-22 00:38:52.971578|
placement_roles           |2025-08-23 05:22:16.042123|
climbs                    |2026-01-31 01:07:23.833934|
climb_stats               |2026-01-31 01:22:10.306067|
beta_links                |2026-01-09 02:29:20.891517|
kits                      |2026-01-22 20:08:48.978201|
 *
 * Possibly when each table in this DB was synced?
 */

SELECT fa_at FROM climb_stats ORDER BY fa_at DESC;

/*
fa_at              |
-------------------+
2026-01-31 01:20:12|
2026-01-31 01:11:42|
2026-01-31 01:07:46|
 *
 * Yep, last logged first ascent agrees with this.
 *
 * This leaves android_meta.
 */

SELECT * FROM android_metadata;
/*
locale|
------+
en_US |
 *
 * Nothing of value here.
 */

-------------------------------------------------------

/*
 * Trying to understand some more about the data.
 *
 * Let's start with udnerstanding more about layouts and placements.
 */

-- How many climbs per layout? What about stats?
SELECT
    c.layout_id,
    COUNT(DISTINCT c.uuid) AS climbs,
    COUNT(cs.climb_uuid) AS stats_rows
FROM climbs c
LEFT JOIN climb_stats cs ON c.uuid = cs.climb_uuid
GROUP BY c.layout_id;

/*
layout_id|climbs|stats_rows|
---------+------+----------+
        9| 68511|     76256|
       10| 39396|     44986|
       11| 20855|     25804|
 *
 * So 68k for the TB1, 39k for TB2 Mirror, and 20k for TB2 spray.
 */

-- How many placements per layout?
SELECT
    layout_id,
    COUNT(*) AS placement_count
FROM placements
GROUP BY layout_id;
/*
layout_id|placement_count|
---------+---------------+
        9|            303|
       10|            498|
       11|            498|
 *
 * This makes sense. I know the TB2 Mirror 12x12 is supposed to have 498 holds.
 *
 * How do the sets relate to the layout?
 */

SELECT
    l.id AS layout_id,
    l.name AS layout_name,
    p.set_id,
    s.name AS set_name,
    COUNT(p.id) AS placement_count
FROM layouts l
JOIN placements p ON l.id = p.layout_id
JOIN sets s ON p.set_id = s.id
GROUP BY l.id, l.name, p.set_id, s.name
ORDER BY l.id, p.set_id;
/*
layout_id|layout_name           |set_id|set_name|placement_count|
---------+----------------------+------+--------+---------------+
        9|Original Layout       |     8|Set A   |             82|
        9|Original Layout       |     9|Set B   |             83|
        9|Original Layout       |    10|Set C   |             84|
        9|Original Layout       |    11|Foot Set|             54|
       10|Tension Board 2 Mirror|    12|Wood    |            242|
       10|Tension Board 2 Mirror|    13|Plastic |            256|
       11|Tension Board 2 Spray |    12|Wood    |            242|
       11|Tension Board 2 Spray |    13|Plastic |            256|
 *
 * So this tells us which sets belong to which board.
 * With the TB2 Mirror, all the wood (242) and plastic (256) add up to 498, as expected.
 */

-- Where do the placements go?
SELECT
    p.id AS placement_id,
    p.layout_id,
    l.name AS layout_name,
    p.hole_id,
    h.name AS hole_name,
    h.x,
    h.y,
    s.name AS set_name
FROM placements p
JOIN holes h ON p.hole_id = h.id
JOIN sets s ON p.set_id = s.id
JOIN layouts l ON p.layout_id = l.id
ORDER BY p.layout_id, p.id;

/*
 placement_id|layout_id|layout_name    |hole_id|hole_name|x |y  |set_name|
------------+---------+---------------+-------+---------+--+---+--------+
           1|        9|Original Layout|      2|B,18     |16|152|Set A   |
           2|        9|Original Layout|     10|J,18     |80|152|Set A   |
           3|        9|Original Layout|    317|B,3      |16| 32|Set A   |
           4|        9|Original Layout|    325|J,3      |80| 32|Set A   |
           5|        9|Original Layout|    320|E,3      |40| 32|Set A   |
 * Okay, so we can figure out from this table a) which board (sepcific layout) b) which hole c) the specific (x,y)-cordinate that the placement goes.
 * Looking at the product_sizes table, we have our coordinate system (x,y). For the TB2, x ranges from -64 to 64 and y from 0 to 144.
 * Note that there are a few inches on the left and right of the board, so this makes sense.
 */

-- How many LEDs total, and by product_size?
SELECT
    ps.id AS product_size_id,
    ps.name AS size_name,
    p.name AS product_name,
    COUNT(l.id) AS led_count
FROM leds l
JOIN product_sizes ps ON l.product_size_id = ps.id
JOIN products p ON ps.product_id = p.id
GROUP BY ps.id, ps.name, p.name
ORDER BY ps.id;
/*
 * There seems to be a discrepency as there are 578 LEDs on the 12x12 TB2, but only 498 holds.
 *
product_size_id|size_name        |product_name   |led_count|
---------------+-----------------+---------------+---------+
              1|Full Wall        |Tension Board  |      389|
              2|Half Kickboard   |Tension Board  |      379|
              3|No Kickboard     |Tension Board  |      368|
              4|Short            |Tension Board  |      305|
              5|Short & Narrow   |Tension Board  |      217|
              6|12 high x 12 wide|Tension Board 2|      578|
              7|10 high x 12 wide|Tension Board 2|      479|
              8|12 high x 8 wide |Tension Board 2|      368|
              9|10 high x 8 wide |Tension Board 2|      305|

 *
 * Looking at the installation guide (https://artrock.at/wp-content/uploads/2026/03/MIRROR_2024_TensionBoard2_InstallGuide_1_22_26.pdf),
 * 	the main grid (17 x 18 = 306) + the subgrid (16 x 17 = 272) adds up to 578.
 *
 * It seems as though we're not using all the holes.
 *
 *
 * Let's dive deeper into the data to unravel this.
 *
 */

-- Check if every hole has an LED
SELECT
    COUNT(DISTINCT h.id) AS total_holes,
    COUNT(DISTINCT l.hole_id) AS holes_with_leds,
    COUNT(DISTINCT h.id) - COUNT(DISTINCT l.hole_id) AS holes_without_leds
FROM holes h
LEFT JOIN leds l ON h.id = l.hole_id;
/*
 *
 total_holes|holes_with_leds|holes_without_leds|
-----------+---------------+------------------+
        967|            967|                 0|
 */



-- For TB2 (product_id=5), which holes are used by layouts vs LEDs?
-- First, what holes does layout 10 use?
SELECT COUNT(DISTINCT p.hole_id) AS holes_in_layout_10
FROM placements p
WHERE p.layout_id = 10;
/*
holes_in_layout_10|
------------------+
               498|
 */

-- What's the hole range for each product?
SELECT
    h.product_id,
    MIN(h.id) AS min_hole_id,
    MAX(h.id) AS max_hole_id,
    COUNT(*) AS total_holes
FROM holes h
GROUP BY h.product_id;

/*
product_id|min_hole_id|max_hole_id|total_holes|
----------+-----------+-----------+-----------+
         4|          1|        389|        389|
         5|        390|        967|        578|
 */


-- Do LED positions overlap or are they sequential per size?
SELECT
    product_size_id,
    MIN(position) AS min_pos,
    MAX(position) AS max_pos,
    COUNT(*) AS led_count
FROM leds
GROUP BY product_size_id
ORDER BY product_size_id;

/*
product_size_id|min_pos|max_pos|led_count|
---------------+-------+-------+---------+
              1|      0|    389|      389|
              2|      0|    389|      379|
              3|     22|    389|      368|
              4|      0|    304|      305|
              5|      0|    216|      217|
              6|      0|    577|      578|
              7|      0|    478|      479|
              8|      0|    367|      368|
              9|      0|    304|      305|
 */

-- Which holes in the TB2 range (390-967) are NOT used by layout 10?
SELECT *
FROM holes h
WHERE h.product_id = 5
AND h.id NOT IN (
    SELECT DISTINCT p.hole_id
    FROM placements p
    WHERE p.layout_id = 10
);

/*
id |product_id|name  |x  |y |mirrored_hole_id|mirror_group|
---+----------+------+---+--+----------------+------------+
391|         5|-64,12|-64|12|             951|           0|
424|         5|-60,8 |-60| 8|             949|           0|
423|         5|-60,16|-60|16|             948|           0|
422|         5|-60,24|-60|24|             947|           0|
416|         5|-60,72|-60|72|             941|           0|
 */


---------------------------------------------------------------
/*
 * So we understand HOW the board works pretty well now. Let's summarize.
 * - There are about 128k climbs, across 3 layouts -- the TB1, TB2 (Mirror) and TB2 (Spray).
 * - There are about 147k statistcs for climbs. This includes multiple angles for each climb.
 * - Some key features are the frames, the angle, and the layout_id (the latter determins the board, the former the actual climb on the board)
 * - Hold positions are decoded via mapping placements to (x,y) coordinates (from the holes tables)
 * - There are four hold types: start, middle, finish, foot. 498 holds on the TB2.
 * - There are different hold sets (e.g., Wood/Plastic on TB2).
 * - LEDs just map on to holes, and light up depending on our frames. There are 80 unused LEDs on the TB2.
 */




