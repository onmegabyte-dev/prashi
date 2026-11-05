-- Sample Prashi Tutorial data. Every value here is a placeholder to replace from the admin panel.
-- Admin and student accounts are NOT here: they're created by scripts/create-admin.js so passwords are hashed.

INSERT INTO settings (key,value,help) VALUES
('site_name','Prashi Tutorial','Shown in the header, footer and browser tab.'),
('tagline','Learn Today. Lead Tomorrow.','Short line under the name on the home page.'),
('phone','+91 90000 00000','PLACEHOLDER – replace with your real number.'),
('whatsapp','919000000000','Digits only, with country code (no + or spaces). Used for the WhatsApp button.'),
('email','hello@prashitutorial.example','PLACEHOLDER – enquiry emails are also sent here.'),
('admin_inbox_email','admin@prashitutorial.example','New enquiries and admissions are emailed to this address.'),
('address','Your branch address, City, State, PIN','PLACEHOLDER – shown on the Contact page and footer.'),
('map_embed_url','','Optional. Paste the Google Maps Embed a map link here. Leave blank to hide the map.'),
('office_hours','Mon–Sat 9 am–7 pm · Sun 10 am–2 pm','Shown on the Contact page.'),
('social_instagram','','Full link, or leave blank to hide.'),
('social_youtube','','Full link, or leave blank to hide.'),
('social_facebook','','Full link, or leave blank to hide.'),
('banner_text','Admissions open for 2026–27','Thin announcement bar at the top. Leave blank for none.'),
('stats_students','10000','Number on the home page counter.'),
('stats_success','95','Success rate % on the home page.'),
('stats_faculty','50','Number of faculty on the home page.'),
('stats_years','15','Years of experience on the home page.');

INSERT INTO faculty (id,name,subject,qualifications,experience,focus,bio,sort_order) VALUES
(1,'Dr. Meera Rao','Physics','Ph.D. IIT Kharagpur','16 yrs','Mechanics, electrodynamics','Taught 4,000+ JEE aspirants; believes every formula should be earned by a question.',1),
(2,'Dr. Anil Sahoo','Biology','MBBS, M.Sc.','14 yrs','Human physiology, genetics','Teaches biology as a story of how the body solves problems.',2),
(3,'Kavita Nayak','Mathematics','M.Sc. Mathematics, B.Ed.','12 yrs','Algebra, Olympiad problems','Known for turning fear of maths into puzzle-solving habits.',3),
(4,'Rohit Patra','Chemistry','M.Sc. IIT Bombay','10 yrs','Organic, physical chemistry','Uses reaction maps so students see the pattern, not just the page.',4),
(5,'Sunita Das','Physics','M.Sc., NET qualified','13 yrs','Board exams, optics','Runs the doubt clinic and knows every board marking scheme.',5),
(6,'Arjun Mishra','Mathematics','B.Tech NIT, M.Tech','9 yrs','Calculus, coordinate geometry','Brings clear logic to hard problems.',6);

INSERT INTO courses (id,slug,name,class_level,exam,course_type,duration,fee_amount,instalments,subjects,highlights,schedule_text,faculty_id,sort_order) VALUES
(1,'jee','JEE Advanced Track','Class 11–12','JEE','Classroom','24 months',145000,4,'Physics,Chemistry,Mathematics','Small batches of 25
Weekly mock tests
Rank-tracking dashboard','Mon–Sat, 4:00–7:00 pm',1,1),
(2,'neet','NEET Achiever','Class 11–12','NEET','Classroom','24 months',135000,4,'Physics,Chemistry,Biology','NCERT line-by-line
Chapter tests
Biology diagram lab','Mon–Sat, 8:00–11:00 am',2,2),
(3,'foundation','Foundation 9–10','Class 9–10','Board','Classroom','12 months',58000,4,'Maths,Science','Concept-first teaching
Olympiad prep included
Monthly parent report','Weekdays 5:00–7:00 pm',3,3),
(4,'olympiad','Olympiad Circle','Class 6–8','Olympiad','Weekend','6 months',24000,2,'Maths,Science','Puzzle-based learning
Math & Science Olympiad papers
Weekend only','Sat–Sun, 10:00 am–12:30 pm',4,4),
(5,'online','Live Online Boards','Class 12','Board','Online','6 months',32000,2,'Physics,Chemistry,Maths','Live classes with recordings
Previous-year paper drills
Daily doubt chat','Evenings 7:00–9:00 pm',5,5),
(6,'crash','JEE Main Crash Course','Class 12','JEE','Online','3 months',18500,1,'Physics,Chemistry,Mathematics','Revision-first
20 full mock tests
Error-log coaching','Daily 6:00–8:00 pm',1,6);

INSERT INTO batches (course_id,name,start_date,timing,seats_total,status) VALUES
(1,'JEE 2026-28 Morning','2026-11-08','Mon–Sat 4:00–7:00 pm',25,'open'),
(2,'NEET 2026-28','2026-11-12','Mon–Sat 8:00–11:00 am',25,'open'),
(3,'Foundation Evening','2026-11-20','Weekdays 5:00–7:00 pm',30,'open'),
(4,'Olympiad Weekend','2026-11-05','Sat–Sun 10:00 am–12:30 pm',30,'open'),
(5,'Online Boards Evening','2026-11-08','Evenings 7:00–9:00 pm',40,'open'),
(6,'JEE Main Crash','2026-11-15','Daily 6:00–8:00 pm',40,'open');

INSERT INTO testimonials (student_name,exam,result_text,quote,rating,approved,sort_order) VALUES
('Ananya S.','NEET 2025','AIR 412','The weekly tests showed exactly where I was losing marks. Doubts were solved the same day.',5,1,1),
('Rahul K.','JEE Advanced 2025','AIR 1,208','Small batch, real attention. My rank tracker kept me honest every week.',5,1,2),
('Priya M.','Class 10 Boards','96.4%','I stopped dreading maths. The teachers explained things until they made sense.',5,1,3),
('Sameer P.','Olympiad','State rank 3','The puzzle sessions were the best part of my week.',4,1,4);

INSERT INTO results (kind,student_name,exam,rank_or_score,year,approved,sort_order) VALUES
('rank','Ananya S.','NEET 2025','AIR 412',2025,1,1),('rank','Rahul K.','JEE Advanced 2025','AIR 1,208',2025,1,2),('rank','Priya M.','Class 10','96.4%',2025,1,3);
INSERT INTO results (kind,year,value,label,approved,sort_order) VALUES
('year_stat',2022,88,'Success rate',1,1),('year_stat',2023,91,'Success rate',1,2),('year_stat',2024,93,'Success rate',1,3),('year_stat',2025,95,'Success rate',1,4),
('improvement',NULL,52,'Mock test 1',1,1),('improvement',NULL,71,'Mock test 10',1,2),('improvement',NULL,89,'Final exam',1,3);

INSERT INTO faqs (question,answer_html,sort_order) VALUES
('How big are the batches?','<p>Classroom batches are capped at 25 students so every child gets attention.</p>',1),
('Is a free demo class available?','<p>Yes. Book a free counselling session and attend one demo class before deciding.</p>',2),
('Can fees be paid in instalments?','<p>Yes. Fees can be paid in instalments. Ask our counsellor for the plan that suits you.</p>',3),
('How are parents kept updated?','<p>Parents get a monthly performance report and can meet teachers on the first Saturday of every month.</p>',4);

INSERT INTO articles (slug,title,category,summary,body_html,published) VALUES
('six-hour-study-day','How to build a 6-hour study day that lasts','Study','Plan around energy, not clock time.','<p>Sample article – edit or replace.</p>',1),
('last-30-days-jee-main','Last 30 days before JEE Main','Exams','A revision order that avoids burnout.','<p>Sample article – edit or replace.</p>',1),
('engineering-or-medicine','Engineering or medicine? A calm way to decide','Career','Questions to ask before choosing.','<p>Sample article – edit or replace.</p>',1),
('error-logs','Making error logs that actually work','Study','Turn every wrong answer into a rule.','<p>Sample article – edit or replace.</p>',1);

-- Form builder: starting fields. 'locked' fields can be re-labelled but not deleted.
INSERT INTO form_fields (form,name,label,type,options,required,sort_order,locked) VALUES
('admission','student_name','Student name','text',NULL,1,1,1),
('admission','phone','Parent phone','tel',NULL,1,2,1),
('admission','email','Email','email',NULL,1,3,0),
('admission','class_level','Class','select','Class 6
Class 7
Class 8
Class 9
Class 10
Class 11
Class 12',1,4,0),
('admission','course','Course','select',NULL,1,5,0),            -- options filled live from the courses table
('enquiry','student_name','Student name','text',NULL,1,1,1),
('enquiry','phone','Phone','tel',NULL,1,2,1),
('enquiry','message','What would you like to know?','textarea',NULL,0,3,0),
('counselling','name','Your name','text',NULL,1,1,1),
('counselling','phone','Phone','tel',NULL,1,2,1),
('contact','name','Name','text',NULL,1,1,1),
('contact','email','Email','email',NULL,1,2,1),
('contact','message','Message','textarea',NULL,1,3,1);
